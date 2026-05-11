import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor  # For parallel fetching

# --- 1. CONFIGURATION ---
BASE_URL = "http://197.243.27.208:9097/api/dataservices/grn"
AUTH_URL = "http://197.243.27.208:9097/api/auth/validate" 

st.set_page_config(page_title="RMS Stock Expiry Dashboard", layout="wide")

# Matching your original HTML design styles
st.markdown("""
    <style>
    .main-header { background:#0D47A1; color:white; padding:20px; text-align:center; font-size:24px; font-weight:bold; border-radius:5px; margin-bottom:10px;}
    .card { background:white; padding:15px; text-align:center; box-shadow:0 2px 4px rgba(0,0,0,0.1); border-top: 5px solid #0D47A1; border-radius:5px; height: 100%; }
    .number { font-size:28px; font-weight:bold; color:#0D47A1; }
    .red-card { border-top-color: #C62828 !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. AUTHENTICATION ---
def get_valid_token():
    if "api_token" in st.session_state:
        return st.session_state.api_token
    try:
        payload = {"username": st.secrets["username"], "password": st.secrets["password"]}
        response = requests.post(AUTH_URL, json=payload, timeout=10)
        response.raise_for_status()
        token = response.json().get("token")
        if token:
            st.session_state.api_token = token 
            return token
    except Exception as e:
        st.error(f"❌ Login Failed: {e}")
        return None

# --- 3. HELPER FOR PARALLEL FETCH ---
def fetch_single_document(doc_id, headers):
    """Function to fetch one document, used by the thread pool."""
    try:
        url = f"{BASE_URL}/{doc_id}"
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            return res.json()
    except:
        return None
    return None

# --- 4. DATA FETCHING (OPTIMIZED) ---
@st.cache_data(ttl=86400)
def fetch_api_data():
    token = get_valid_token()
    if not token:
        return pd.DataFrame()

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    try:
        # Step A: Get all GRN Document IDs
        res = requests.get(BASE_URL, headers=headers, timeout=15)
        res.raise_for_status()
        docs = res.json().get("items", [])
        doc_ids = [d.get("materialDocument") for d in docs if d.get("materialDocument")]
        
        all_items = []
        st.info(f"🚀 Speed-fetching {len(doc_ids)} documents in parallel...")
        
        # Step B: Parallel Fetching using ThreadPoolExecutor
        # This opens 20 connections at once
        with ThreadPoolExecutor(max_workers=20) as executor:
            # Map the fetch function to all IDs
            results = list(executor.map(lambda id: fetch_single_document(id, headers), doc_ids))
        
        # Step C: Process results
        for data in results:
            if data:
                items_list = data if isinstance(data, list) else [data]
                for item in items_list:
                    all_items.append({
                        "Material": item.get("material"),
                        "Description": item.get("materialName", "N/A"),
                        "Units": float(item.get("quantity", 0)),
                        "Plant": item.get("plant", "Unknown"),
                        "Expiry": pd.to_datetime(item.get("expiryDate"), errors='coerce'),
                        "TotalValue": float(item.get("quantity", 0)) * float(item.get("unitCost", 0))
                    })
        
        return pd.DataFrame(all_items)
    except Exception as e:
        st.error(f"⚠️ API Error: {e}")
        return pd.DataFrame()

# --- 5. UI LAYOUT ---
if st.sidebar.button('🔄 Manual Refresh'):
    st.cache_data.clear()
    st.rerun()

df = fetch_api_data()

if not df.empty:
    today = datetime.now()
    df = df.dropna(subset=['Expiry'])
    exp_3m = df[df['Expiry'] <= (today + timedelta(days=90))]
    exp_6m = df[df['Expiry'] <= (today + timedelta(days=180))]

    st.markdown('<div class="main-header">RMS Stock Expiry Dashboard (Live API)</div>', unsafe_allow_html=True)
    
    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(f'<div class="card"><h3>Total Units</h3><div class="number">{df["Units"].sum()/1e6:.2f}M</div></div>', unsafe_allow_html=True)
    k2.markdown(f'<div class="card"><h3>Total SKUs</h3><div class="number">{df["Material"].nunique()}</div></div>', unsafe_allow_html=True)
    k3.markdown(f'<div class="card red-card"><h3>3M Expiry Risk</h3><div class="number">{exp_3m["TotalValue"].sum()/1e9:.2f}B</div></div>', unsafe_allow_html=True)
    k4.markdown(f'<div class="card red-card"><h3>6M Expiry Risk</h3><div class="number">{exp_6m["TotalValue"].sum()/1e9:.2f}B</div></div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Top 10 Expiring Materials (3 Months)")
        top_10 = exp_3m.groupby("Description")["TotalValue"].sum().nlargest(10).reset_index()
        fig1 = px.bar(top_10, x="TotalValue", y="Description", orientation='h', color_discrete_sequence=['#E53935'])
        st.plotly_chart(fig1, use_container_width=True)
    
    with c2:
        st.subheader("Inventory Value by Plant")
        plant_val = df.groupby("Plant")["TotalValue"].sum().reset_index()
        fig2 = px.pie(plant_val, names="Plant", values="TotalValue", hole=0.4)
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("### 📋 Branch Inventory Analysis")
    for plant in sorted(df['Plant'].unique()):
        with st.expander(f"Plant: {plant} - Imminent Expiries (3 Months)"):
            plant_data = exp_3m[exp_3m['Plant'] == plant]
            if not plant_data.empty:
                display_df = plant_data[['Material', 'Description', 'Expiry', 'Units', 'TotalValue']].copy()
                display_df['Expiry'] = display_df['Expiry'].dt.strftime('%d-%b-%Y')
                st.table(display_df)
            else:
                st.info("No items expiring soon.")
else:
    st.info("Waiting for data...")
