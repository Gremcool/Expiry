import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import threading

# --- 1. CONFIGURATION ---
BASE_URL = "http://197.243.27.208:9097/api/dataservices/grn"
AUTH_URL = "http://197.243.27.208:9097/api/auth/validate"

st.set_page_config(page_title="RMS Stock Dashboard", layout="wide")

# --- 2. CSS STYLING (Matching your HTML) ---
st.markdown("""
    <style>
    .main-header { background:#0D47A1; color:white; padding:20px; text-align:center; font-size:24px; font-weight:bold; }
    .card { background:white; padding:15px; text-align:center; box-shadow:0 2px 4px rgba(0,0,0,0.1); border-top: 5px solid #0D47A1; border-radius:5px; }
    .number { font-size:28px; font-weight:bold; color:#0D47A1; }
    .red-card { border-top-color: #C62828 !important; }
    </style>
""", unsafe_allow_html=True)

# --- 3. AUTHENTICATION ---
@st.cache_data(ttl=3600)
def get_token():
    try:
        res = requests.post(AUTH_URL, json={
            "username": st.secrets["username"], 
            "password": st.secrets["password"]
        }, timeout=10)
        return res.json().get("token")
    except: return None

# --- 4. FAST DATA FETCHING ---
def fetch_item_detail(doc_id, token):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(f"{BASE_URL}/{doc_id}", headers=headers, timeout=10)
        return r.json() if r.status_code == 200 else None
    except: return None

@st.cache_data(persist="disk", ttl=86400) # Saves to disk so it's instant for 24 hours
def get_full_dashboard_data(token):
    headers = {"Authorization": f"Bearer {token}"}
    # 1. Get Headers
    res = requests.get(BASE_URL, headers=headers, timeout=20)
    raw_items = res.json().get("items", [])
    doc_ids = [d.get("materialDocument") for d in raw_items if d.get("materialDocument")]
    
    # 2. Parallel Fetch (The Speed Trick)
    all_rows = []
    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(lambda x: fetch_item_detail(x, token), doc_ids))
    
    for data in results:
        if data:
            items = data if isinstance(data, list) else [data]
            for i in items:
                all_rows.append({
                    "Material": i.get("material"),
                    "Description": i.get("materialName"),
                    "Units": float(i.get("quantity", 0)),
                    "Plant": i.get("plant"),
                    "Expiry": pd.to_datetime(i.get("expiryDate"), errors='coerce'),
                    "Value": float(i.get("quantity", 0)) * float(i.get("unitCost", 0))
                })
    return pd.DataFrame(all_rows)

# --- 5. UI LOGIC ---
st.markdown('<div class="main-header">RMS Stock Expiry Dashboard</div>', unsafe_allow_html=True)

token = get_token()
if token:
    # This block triggers the cache. If data is on disk, it returns in 0.1s
    with st.spinner("⚡ Syncing with RMS Data Services..."):
        df = get_full_dashboard_data(token)

    if not df.empty:
        today = datetime.now()
        exp_3m = df[df['Expiry'] <= (today + timedelta(days=90))]
        
        # KPI Row
        k1, k2, k3 = st.columns(3)
        k1.markdown(f'<div class="card"><h3>Total Units</h3><div class="number">{df["Units"].sum()/1e6:.2f}M</div></div>', unsafe_allow_html=True)
        k2.markdown(f'<div class="card"><h3>Active SKUs</h3><div class="number">{df["Material"].nunique()}</div></div>', unsafe_allow_html=True)
        k3.markdown(f'<div class="card red-card"><h3>3M Expiry Risk</h3><div class="number">{exp_3m["Value"].sum()/1e9:.2f}B</div></div>', unsafe_allow_html=True)

        st.divider()
        st.subheader("📋 Plant-wise Risk Breakdown")
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("No data found. Try the refresh button.")
else:
    st.error("Authentication Failed. Check Secrets.")

if st.sidebar.button("🔄 Force Refresh"):
    st.cache_data.clear()
    st.rerun()
