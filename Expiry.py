import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import threading

# --- CONFIGURATION ---
BASE_URL = "http://197.243.27.208:9097/api/dataservices/grn"
AUTH_URL = "http://197.243.27.208:9097/api/auth/validate"

st.set_page_config(page_title="RMS Stock Dashboard", layout="wide")

# --- CSS STYLING (Matches your HTML exactly) ---
st.markdown("""
    <style>
    .main-header { background:#0D47A1; color:white; padding:20px; text-align:center; font-size:24px; font-weight:bold; }
    .card { background:white; padding:15px; text-align:center; box-shadow:0 2px 4px rgba(0,0,0,0.1); border-top: 5px solid #0D47A1; border-radius:5px; }
    .number { font-size:28px; font-weight:bold; color:#0D47A1; }
    .red-card { border-top-color: #C62828 !important; }
    </style>
""", unsafe_allow_html=True)

# --- AUTHENTICATION ---
@st.cache_data(ttl=3600)
def get_token():
    try:
        res = requests.post(AUTH_URL, json={"username": st.secrets["username"], "password": st.secrets["password"]}, timeout=10)
        return res.json().get("token")
    except: return None

# --- FAST HEADER FETCH ---
@st.cache_data(ttl=86400) # Once a day
def fetch_headers(token):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        res = requests.get(BASE_URL, headers=headers, timeout=20)
        return res.json().get("items", [])
    except: return []

# --- BACKGROUND ITEM FETCH ---
def fetch_and_store_details(doc_ids, token):
    headers = {"Authorization": f"Bearer {token}"}
    def fetch_item(did):
        try:
            r = requests.get(f"{BASE_URL}/{did}", headers=headers, timeout=10)
            return r.json() if r.status_code == 200 else None
        except: return None

    with ThreadPoolExecutor(max_workers=15) as executor:
        results = list(executor.map(fetch_item, doc_ids))
    
    # Store in session state so UI picks it up
    new_data = []
    for data in results:
        if data:
            items = data if isinstance(data, list) else [data]
            for i in items:
                new_data.append({
                    "Material": i.get("material"),
                    "Description": i.get("materialName"),
                    "Units": float(i.get("quantity", 0)),
                    "Plant": i.get("plant"),
                    "Expiry": pd.to_datetime(i.get("expiryDate"), errors='coerce'),
                    "Value": float(i.get("quantity", 0)) * float(i.get("unitCost", 0))
                })
    st.session_state['full_df'] = pd.DataFrame(new_data)
    st.session_state['loading_complete'] = True

# --- UI LOGIC ---
st.markdown('<div class="main-header">RMS Stock Expiry Dashboard</div>', unsafe_allow_html=True)

token = get_token()
if token:
    raw_headers = fetch_headers(token)
    
    # Initialize background process if not started
    if 'full_df' not in st.session_state:
        st.session_state['full_df'] = pd.DataFrame()
        st.session_state['loading_complete'] = False
        doc_ids = [d.get("materialDocument") for d in raw_headers if d.get("materialDocument")]
        # Start background thread
        thread = threading.Thread(target=fetch_and_store_details, args=(doc_ids, token))
        thread.start()

    # --- KPI CALCULATIONS ---
    df = st.session_state['full_df']
    
    if not df.empty:
        today = datetime.now()
        exp_3m = df[df['Expiry'] <= (today + timedelta(days=90))]
        exp_6m = df[df['Expiry'] <= (today + timedelta(days=180))]

        # Row 1: Instant Metrics
        k1, k2, k3, k4 = st.columns(4)
        k1.markdown(f'<div class="card"><h3>Active SKUs</h3><div class="number">{df["Material"].nunique()}</div></div>', unsafe_allow_html=True)
        k2.markdown(f'<div class="card"><h3>Total Units</h3><div class="number">{df["Units"].sum()/1e6:.2f}M</div></div>', unsafe_allow_html=True)
        k3.markdown(f'<div class="card red-card"><h3>3M Risk Value</h3><div class="number">{exp_3m["Value"].sum()/1e9:.2f}B</div></div>', unsafe_allow_html=True)
        k4.markdown(f'<div class="card red-card"><h3>6M Risk Value</h3><div class="number">{exp_6m["Value"].sum()/1e9:.2f}B</div></div>', unsafe_allow_html=True)

        st.divider()

        # Row 2: Branch Risk (Matches your HTML tables)
        st.subheader("📋 3-Month Branch Risk Analysis")
        plants = sorted(df['Plant'].unique())
        for plant in plants:
            with st.expander(f"Plant {plant} Details"):
                p_data = exp_3m[exp_3m['Plant'] == plant]
                st.table(p_data[['Material', 'Description', 'Expiry', 'Units', 'Value']])
        
    else:
        st.info("⚡ System is fetching detailed expiries in the background. KPIs will appear here in a few seconds...")
        st.metric("Total Documents Found", len(raw_headers))

    # Auto-refresh UI until background thread is done
    if not st.session_state['loading_complete']:
        st.empty()
        st.rerun()

else:
    st.error("Authentication Failed.")

if st.sidebar.button("🔄 Manual Data Refresh"):
    st.cache_data.clear()
    if 'full_df' in st.session_state: del st.session_state['full_df']
    st.rerun()
