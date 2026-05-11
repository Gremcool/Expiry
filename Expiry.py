import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import hashlib

# --- 1. CONFIGURATION ---
BASE_URL = "http://197.243.27.208:9097/api/dataservices/grn"
AUTH_URL = "http://197.243.27.208:9097/api/auth/validate" 

st.set_page_config(page_title="RMS Live Inventory", layout="wide")

# Matching your Dashboard CSS
st.markdown("""
    <style>
    .main-header { background:#0D47A1; color:white; padding:20px; text-align:center; font-size:24px; font-weight:bold; border-radius:5px; margin-bottom:10px;}
    .card { background:white; padding:15px; text-align:center; box-shadow:0 2px 4px rgba(0,0,0,0.1); border-top: 5px solid #0D47A1; border-radius:5px; height: 100%; }
    .number { font-size:28px; font-weight:bold; color:#0D47A1; }
    </style>
""", unsafe_allow_html=True)

# --- 2. FAST AUTHENTICATION ---
@st.cache_data(ttl=3600) # Only log in once per hour
def get_auth_token():
    try:
        payload = {"username": st.secrets["username"], "password": st.secrets["password"]}
        response = requests.post(AUTH_URL, json=payload, timeout=10)
        return response.json().get("token")
    except:
        return None

# --- 3. THE "LISTEN" TRICK (Takes < 1 second) ---
def get_api_fingerprint(token):
    """Fetches ONLY the header list to see if anything changed."""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        res = requests.get(BASE_URL, headers=headers, timeout=15)
        items = res.json().get("items", [])
        # Create a unique ID for this specific set of data
        fingerprint = hashlib.md5(str(items).encode()).hexdigest()
        return fingerprint, items
    except:
        return None, []

# --- 4. PARALLEL DATA PROCESSING ---
def fetch_item_detail(doc_id, headers):
    try:
        res = requests.get(f"{BASE_URL}/{doc_id}", headers=headers, timeout=10)
        return res.json() if res.status_code == 200 else None
    except:
        return None

@st.cache_data(persist="disk") # This saves the data to the server disk
def get_cached_full_data(items_list, token):
    """This is the 'slow' part that only runs when data is updated."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    doc_ids = [d.get("materialDocument") for d in items_list if d.get("materialDocument")]
    
    # Use 50 workers to blast through the requests in parallel
    with ThreadPoolExecutor(max_workers=50) as executor:
        results = list(executor.map(lambda id: fetch_item_detail(id, headers), doc_ids))
    
    all_rows = []
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

# --- 5. MAIN EXECUTION LOGIC ---
token = get_auth_token()
if token:
    # Quick check: Has the data changed on the server?
    current_fp, raw_items = get_api_fingerprint(token)
    
    # If this is a new session or data changed, refresh
    if "last_fp" not in st.session_state or st.session_state.last_fp != current_fp:
        st.session_state.last_fp = current_fp
        # This only runs once when data changes
        df = get_cached_full_data(raw_items, token)
    else:
        # This loads instantly (< 0.5s)
        df = get_cached_full_data(raw_items, token)

    # --- 6. DISPLAY DASHBOARD ---
    if not df.empty:
        st.markdown('<div class="main-header">RMS Live Inventory Dashboard</div>', unsafe_allow_html=True)
        
        # Logic for 3M/6M risk
        today = datetime.now()
        df = df.dropna(subset=['Expiry'])
        exp_3m = df[df['Expiry'] <= (today + timedelta(days=90))]
        
        # KPI Row
        col1, col2, col3 = st.columns(3)
        col1.markdown(f'<div class="card"><h3>Total Units</h3><div class="number">{df["Units"].sum()/1e6:.2f}M</div></div>', unsafe_allow_html=True)
        col2.markdown(f'<div class="card"><h3>Active SKUs</h3><div class="number">{df["Material"].nunique()}</div></div>', unsafe_allow_html=True)
        col3.markdown(f'<div class="card" style="border-top-color:red"><h3>3M Expiry Risk</h3><div class="number">{exp_3m["TotalValue"].sum()/1e9:.2f}B</div></div>', unsafe_allow_html=True)
        
        st.write("---")
        st.subheader("📋 Inventory by Material and Plant")
        st.dataframe(df, use_container_width=True)
        
        st.success(f"⚡ Instant Load: Data is synced with API. Last check: {datetime.now().strftime('%H:%M:%S')}")
else:
    st.error("Could not authenticate with API.")

# Sidebar Refresh
if st.sidebar.button("🔄 Force API Re-Sync"):
    st.cache_data.clear()
    st.rerun()
