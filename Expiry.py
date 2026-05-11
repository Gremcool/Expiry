import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

# --- 1. CONFIGURATION ---
BASE_URL = "http://197.243.27.208:9097/api/dataservices/grn"
AUTH_URL = "http://197.243.27.208:9097/api/login" # Verify this URL with your dev team

st.set_page_config(page_title="RMS API Dashboard", layout="wide")

# Matching your original HTML design styles
st.markdown("""
    <style>
    .main-header { background:#0D47A1; color:white; padding:20px; text-align:center; font-size:24px; font-weight:bold; border-radius:5px; margin-bottom:10px;}
    .card { background:white; padding:15px; text-align:center; box-shadow:0 2px 4px rgba(0,0,0,0.1); border-top: 5px solid #0D47A1; border-radius:5px; height: 100%; }
    .number { font-size:28px; font-weight:bold; color:#0D47A1; }
    .stTable { font-size: 12px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. AUTHENTICATION LOGIC ---
def get_valid_token():
    """Exchange credentials for a fresh Bearer token."""
    if "api_token" in st.session_state:
        return st.session_state.api_token

    try:
        # Fetch credentials securely
        payload = {
            "username": st.secrets["username"],
            "password": st.secrets["password"]
        }
        response = requests.post(AUTH_URL, json=payload, timeout=10)
        response.raise_for_status()
        
        token = response.json().get("token")
        # Store in session so we don't login on every tiny UI change
        st.session_state.api_token = token 
        return token
    except Exception as e:
        st.error(f"Authentication Failed: {e}")
        return None

# --- 3. DATA FETCHING (Combined Header & Item Level) ---
@st.cache_data(ttl=86400) # Only calls API once every 24 hours
def fetch_dashboard_data():
    token = get_valid_token()
    if not token:
        return pd.DataFrame()

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    try:
        # Step A: Get all GRN Document IDs
        res = requests.get(BASE_URL, headers=headers, timeout=15)
        res.raise_for_status()
        docs = res.json().get("items", [])
        
        all_items = []
        progress_bar = st.progress(0, "Fetching detailed stock data...")
        
        # Step B: Loop to get Item Level details (Expiries)
        for i, doc in enumerate(docs):
            doc_id = doc.get("materialDocument")
            if doc_id:
                item_res = requests.get(f"{BASE_URL}/{doc_id}", headers=headers, timeout=10)
                if item_res.status_code == 200:
                    data = item_res.json()
                    # Flatten the response if it's a list of materials inside one document
                    items_list = data if isinstance(data, list) else [data]
                    for item in items_list:
                        all_items.append({
                            "Material": item.get("material"),
                            "Description": item.get("materialName"),
                            "Units": float(item.get("quantity", 0)),
                            "Plant": item.get("plant"),
                            "Expiry": pd.to_datetime(item.get("expiryDate"), errors='coerce'),
                            "TotalValue": float(item.get("quantity", 0)) * float(item.get("unitCost", 0))
                        })
            progress_bar.progress((i + 1) / len(docs))
        
        progress_bar.empty()
        return pd.DataFrame(all_items)
    except Exception as e:
        # If token expired during fetch, clear it so next refresh logs in again
        if "401" in str(e):
            del st.session_state.api_token
        st.error(f"Data Fetch Error: {e}")
        return pd.DataFrame()

# --- 4. DASHBOARD UI ---
if st.sidebar.button('🔄 Refresh from API'):
    st.cache_data.clear()
    st.rerun()

df = fetch_dashboard_data()

if not df.empty:
    # Logic for 3M/6M projections
    today = datetime.now()
    df = df.dropna(subset=['Expiry'])
    exp_3m = df[df['Expiry'] <= (today + timedelta(days=90))]
    exp_6m = df[df['Expiry'] <= (today + timedelta(days=180))]

    st.markdown('<div class="main-header">RMS Stock Expiry Dashboard (Live API)</div>', unsafe_allow_html=True)
    
    # KPI Cards
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.markdown(f'<div class="card"><h3>Total Units</h3><div class="number">{df["Units"].sum()/1e6:.2f}M</div></div>', unsafe_allow_html=True)
    kpi2.markdown(f'<div class="card"><h3>Active SKUs</h3><div class="number">{df["Material"].nunique()}</div></div>', unsafe_allow_html=True)
    kpi3.markdown(f'<div class="card" style="border-top-color:#C62828"><h3>3M Expiring Value</h3><div class="number">{exp_3m["TotalValue"].sum()/1e9:.2f}B</div></div>', unsafe_allow_html=True)
    kpi4.markdown(f'<div class="card" style="border-top-color:#C62828"><h3>6M Expiring Value</h3><div class="number">{exp_6m["TotalValue"].sum()/1e9:.2f}B</div></div>', unsafe_allow_html=True)

    # Charts
    st.write("---")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Top 10 Expiring (3M) by Value")
        chart_data = exp_3m.groupby("Description")["TotalValue"].sum().nlargest(10).reset_index()
        fig = px.bar(chart_data, x="TotalValue", y="Description", orientation='h', color_discrete_sequence=['#E53935'])
        st.plotly_chart(fig, use_container_width=True)
    
    with c2:
        st.subheader("Expiry Risk by Plant")
        plant_risk = exp_3m.groupby("Plant")["TotalValue"].sum().reset_index()
        fig2 = px.pie(plant_risk, names="Plant", values="TotalValue", hole=0.5)
        st.plotly_chart(fig2, use_container_width=True)

    # Risk Tables
    st.markdown("### 🔍 Detailed Plant Risk Analysis")
    for plant in sorted(df['Plant'].unique()):
        with st.expander(f"Plant {plant} - Imminent Expiries"):
            p_data = exp_3m[exp_3m['Plant'] == plant]
            if not p_data.empty:
                st.dataframe(p_data[['Material', 'Description', 'Expiry', 'Units', 'TotalValue']], use_container_width=True)
            else:
                st.info("No items expiring within 3 months for this plant.")
else:
    st.info("No data available. Use the sidebar to refresh.")