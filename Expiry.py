import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import hashlib

# --- 1. CONFIGURATION ---
BASE_URL = "http://197.243.27.208:9097/api/dataservices/grn"
AUTH_URL = "http://197.243.27.208:9097/api/auth/validate" 

st.set_page_config(page_title="RMS Inventory", layout="wide")

# Persistent styling
st.markdown("""
    <style>
    .main-header { background:#0D47A1; color:white; padding:20px; text-align:center; font-size:24px; font-weight:bold; border-radius:5px; }
    .card { background:white; padding:15px; text-align:center; box-shadow:0 2px 4px rgba(0,0,0,0.1); border-top: 5px solid #0D47A1; border-radius:5px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. AUTHENTICATION ---
@st.cache_data(ttl=3600)
def get_token():
    try:
        res = requests.post(AUTH_URL, json={
            "username": st.secrets["username"],
            "password": st.secrets["password"]
        }, timeout=15)
        return res.json().get("token")
    except:
        return None

# --- 3. DATA FETCHING ---
def fetch_details(doc_id, headers):
    try:
        r = requests.get(f"{BASE_URL}/{doc_id}", headers=headers, timeout=15)
        return r.json() if r.status_code == 200 else None
    except:
        return None

@st.cache_data(persist="disk") # Instant load from disk if fingerprint matches
def get_data_sync(items_list, token):
    headers = {"Authorization": f"Bearer {token}"}
    doc_ids = [d.get("materialDocument") for d in items_list if d.get("materialDocument")]
    
    # We use 10 workers instead of 50 to avoid timing out the cloud connection
    all_rows = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(lambda x: fetch_details(x, headers), doc_ids))
    
    for data in results:
        if data:
            items = data if isinstance(data, list) else [data]
            for i in items:
                all_rows.append({
                    "Material": i.get("material"),
                    "Description": i.get("materialName", "N/A"),
                    "Units": float(i.get("quantity", 0)),
                    "Plant": i.get("plant", "Unknown"),
                    "Expiry": pd.to_datetime(i.get("expiryDate"), errors='coerce'),
                    "TotalValue": float(i.get("quantity", 0)) * float(i.get("unitCost", 0))
                })
    return pd.DataFrame(all_rows)

# --- 4. MAIN UI LOGIC ---
st.markdown('<div class="main-header">RMS Stock Expiry Dashboard</div>', unsafe_allow_html=True)

token = get_token()
if token:
    # Use a status box so the page isn't blank while checking for updates
    with st.status("📡 Checking for API updates...", expanded=True) as status:
        headers = {"Authorization": f"Bearer {token}"}
        try:
            # 1. Light fetch (the 12s one from your image)
            res = requests.get(BASE_URL, headers=headers, timeout=20)
            raw_items = res.json().get("items", [])
            
            # 2. Fingerprint check
            new_fp = hashlib.md5(str(raw_items).encode()).hexdigest()
            
            if "fp" not in st.session_state or st.session_state.fp != new_fp:
                st.write("🔄 New data detected. Syncing item details...")
                st.session_state.fp = new_fp
                df = get_data_sync(raw_items, token)
            else:
                st.write("✅ No changes in API. Loading from cache...")
                df = get_data_sync(raw_items, token)
            
            status.update(label="✅ Data Synced!", state="complete", expanded=False)
        except Exception as e:
            st.error(f"Connection Error: {e}")
            df = pd.DataFrame()

    # --- 5. RENDER DASHBOARD ---
    if not df.empty:
        df = df.dropna(subset=['Expiry'])
        exp_3m = df[df['Expiry'] <= (datetime.now() + timedelta(days=90))]
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Units", f"{df['Units'].sum()/1e6:.2f}M")
        c2.metric("Active SKUs", df['Material'].nunique())
        c3.metric("3M Risk Value", f"{exp_3m['TotalValue'].sum()/1e9:.2f}B")
        
        st.subheader("📋 Master Inventory Data")
        st.dataframe(df, use_container_width=True)
else:
    st.error("Authentication failed. Check your Secrets.")

if st.sidebar.button("Force Refresh"):
    st.cache_data.clear()
    st.rerun()
