import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="RMS Dashboard", layout="wide")

# Styling
st.markdown('<style>.main-header { background:#0D47A1; color:white; padding:20px; text-align:center; font-size:24px; font-weight:bold; }</style>', unsafe_allow_html=True)
st.markdown('<div class="main-header">RMS Stock Expiry Dashboard (Instant Load)</div>', unsafe_allow_html=True)

try:
    # INSTANT LOADING: Reading local file instead of API
    df = pd.read_csv("expiry_data.csv")
    df['Expiry'] = pd.to_datetime(df['Expiry'], errors='coerce')
    df['TotalValue'] = df['Units'] * df['unitCost']
    
    # Metrics
    today = datetime.now()
    exp_3m = df[df['Expiry'] <= (today + timedelta(days=90))]
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Units", f"{df['Units'].sum()/1e6:.2f}M")
    c2.metric("Active SKUs", df['Material'].nunique())
    c3.metric("3M Risk Value", f"{exp_3m['TotalValue'].sum()/1e9:.2f}B")

    st.subheader("📋 Inventory Risk Table")
    st.dataframe(df, use_container_width=True)
    
    # Show last sync time
    st.caption(f"Last API Sync: {datetime.fromtimestamp(os.path.getmtime('expiry_data.csv')).strftime('%Y-%m-%d %H:%M:%S')}")

except Exception as e:
    st.error("Data file not found. Please wait for the first nightly sync to complete.")
