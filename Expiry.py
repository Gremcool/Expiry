import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os

st.set_page_config(page_title="RMS Stock Dashboard", layout="wide")

# CSS Styling (Matches your HTML)
st.markdown("""
    <style>
    .main-header { background:#0D47A1; color:white; padding:20px; text-align:center; font-size:24px; font-weight:bold; border-radius: 5px; }
    .sub-banner { background:#E3F2FD; border: 1px solid #2196F3; color:#0D47A1; padding:8px; text-align:center; font-size:14px; font-weight:bold; margin-bottom:20px; border-radius:4px; }
    .card { background:white; padding:15px; text-align:center; box-shadow:0 2px 4px rgba(0,0,0,0.1); border-top: 5px solid #0D47A1; border-radius:5px; }
    .card.red { border-top-color: #C62828; }
    .card h3 { font-size: 13px; color: #555; margin-bottom: 8px; }
    .card .number { font-size:26px; font-weight:bold; color:#0D47A1; }
    .card.red .number { color: #C62828; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">RMS Stock Expiry Dashboard</div>', unsafe_allow_html=True)

DATA_FILE = "expiry_data.csv"

if os.path.exists(DATA_FILE):
    df = pd.read_csv(DATA_FILE)
    
    # SAFETY CHECK: Ensure Branch column exists to avoid KeyError
    if 'Branch' not in df.columns:
        st.info("🔄 Update in progress: The background sync is adding Branch Names to the data. Please wait 2 minutes and refresh.")
        st.stop()

    df['Expiry'] = pd.to_datetime(df['Expiry'], errors='coerce')
    df['Total Value'] = df['Units'] * df['unitCost']
    exp_3m = df[df['Expiry'] <= (datetime.now() + timedelta(days=90))]
    
    # KPI Cards
    c1, c2, c3 = st.columns(3)
    c1.markdown(f'<div class="card"><h3>Total Units</h3><div class="number">{df["Units"].sum()/1e6:.2f}M</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="card"><h3>Active SKUs</h3><div class="number">{df["Material"].nunique()}</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="card red"><h3>3M Risk Value</h3><div class="number">{exp_3m["Total Value"].sum()/1e9:.2f}B</div></div>', unsafe_allow_html=True)

    st.write("---")
    st.subheader("📋 Branch Inventory Risk Analysis")
    
    branches = df[['Plant', 'Branch']].drop_duplicates().sort_values('Plant')
    for _, row in branches.iterrows():
        p_id, b_name = row['Plant'], row['Branch']
        p_data = exp_3m[exp_3m['Plant'] == p_id].sort_values('Total Value', ascending=False)
        
        if not p_data.empty:
            # LOOKS LIKE YOUR HTML: Plant ID | Branch Name
            with st.expander(f"Plant: {int(p_id)} | Branch: {b_name} (3-Month Outlook)"):
                display = p_data[['Material', 'Description', 'Expiry', 'Units', 'Total Value']].copy()
                display['Expiry'] = display['Expiry'].dt.strftime('%d-%b-%Y')
                st.table(display.style.format({'Units': '{:,.0f}', 'Total Value': '{:,.0f}'}))
else:
    st.error("Data file not found. Please trigger the manual sync in GitHub Actions.")
