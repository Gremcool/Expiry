import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os

st.set_page_config(page_title="RMS Stock Dashboard", layout="wide")

# CSS Styling to match your HTML
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
st.markdown('<div class="sub-banner">Branch-Mapped Inventory Risk Outlook</div>', unsafe_allow_html=True)

DATA_FILE = "expiry_data.csv"

if os.path.exists(DATA_FILE):
    df = pd.read_csv(DATA_FILE)
    df['Expiry'] = pd.to_datetime(df['Expiry'], errors='coerce')
    df['Total Value'] = df['Units'] * df['unitCost']
    
    today = datetime.now()
    exp_3m = df[df['Expiry'] <= (today + timedelta(days=90))]
    
    # KPI Row
    c1, c2, c3 = st.columns(3)
    c1.markdown(f'<div class="card"><h3>Total Units</h3><div class="number">{df["Units"].sum()/1e6:.2f}M</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="card"><h3>Active SKUs</h3><div class="number">{df["Material"].nunique()}</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="card red"><h3>3M Risk Value</h3><div class="number">{exp_3m["Total Value"].sum()/1e9:.2f}B</div></div>', unsafe_allow_html=True)

    st.write("---")
    st.subheader("📋 Branch Inventory (3-Month Risk Analysis)")
    
    # Grouping by Plant AND Branch Name
    branches = df[['Plant', 'Branch']].drop_duplicates().sort_values('Plant')
    
    for _, row in branches.iterrows():
        plant_id = row['Plant']
        branch_name = row['Branch']
        
        branch_data = exp_3m[exp_3m['Plant'] == plant_id].sort_values('Total Value', ascending=False)
        
        if not branch_data.empty:
            # Replicating your HTML Branch Headers
            with st.expander(f"Plant: {int(plant_id)} | Branch: {branch_name} (3-Month Outlook)"):
                display_df = branch_data[['Material', 'Description', 'Expiry', 'Units', 'Total Value']].copy()
                display_df['Expiry'] = display_df['Expiry'].dt.strftime('%d-%b-%Y')
                st.table(display_df.style.format({'Units': '{:,.0f}', 'Total Value': '{:,.0f}'}))
else:
    st.error("Data file not found. Ensure the nightly sync has run.")
