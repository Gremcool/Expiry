import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="RMS Stock Dashboard", layout="wide")

# --- 2. CUSTOM CSS (Matching your HTML perfectly) ---
st.markdown("""
    <style>
    /* Main Header */
    .main-header { 
        background:#0D47A1; color:white; padding:20px; 
        text-align:center; font-size:24px; font-weight:bold; 
        margin-bottom:10px; border-radius: 5px;
    }
    /* Sub Banner */
    .sub-banner { 
        background:#E3F2FD; border: 1px solid #2196F3; 
        color:#0D47A1; padding:8px; text-align:center; 
        font-size:14px; font-weight:bold; margin-bottom:20px; border-radius:4px; 
    }
    /* KPI Cards */
    .card { 
        background:white; padding:15px; text-align:center; 
        box-shadow:0 2px 4px rgba(0,0,0,0.1); 
        border-top: 5px solid #0D47A1; border-radius:5px;
        min-height: 120px;
    }
    .card.green { border-top-color: #2E7D32; }
    .card.red { border-top-color: #C62828; }
    .card h3 { font-size: 13px; margin-bottom: 10px; color: #555; }
    .card .number { font-size:26px; font-weight:bold; color:#0D47A1; }
    .card.green .number { color: #2E7D32; }
    .card.red .number { color: #C62828; }
    
    /* Tables */
    .styled-table { font-size: 12px; }
    </style>
""", unsafe_allow_html=True)

# --- 3. HEADER UI ---
st.markdown('<div class="main-header">RMS Stock Expiry Dashboard</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-banner">Stock Data Synced via Background API Bridge</div>', unsafe_allow_html=True)

# --- 4. DATA LOADING ---
DATA_FILE = "expiry_data.csv"

if os.path.exists(DATA_FILE):
    df = pd.read_csv(DATA_FILE)
    df['Expiry'] = pd.to_datetime(df['Expiry'], errors='coerce')
    df['Total Value'] = df['Units'] * df['unitCost']
    
    # --- 5. KPI CALCULATIONS ---
    today = datetime.now()
    exp_3m = df[df['Expiry'] <= (today + timedelta(days=90))]
    exp_6m = df[df['Expiry'] <= (today + timedelta(days=180))]
    
    # KPI Row 1
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f'<div class="card"><h3>Total Units</h3><div class="number">{df["Units"].sum()/1e6:.2f}M</div></div>', unsafe_allow_html=True)
    with k2:
        st.markdown(f'<div class="card"><h3>Total SKUs</h3><div class="number">{df["Material"].nunique()}</div></div>', unsafe_allow_html=True)
    with k3:
        st.markdown(f'<div class="card green"><h3>Current Inventory Value</h3><div class="number">{df["Total Value"].sum()/1e9:.2f}B</div></div>', unsafe_allow_html=True)
    with k4:
        st.markdown(f'<div class="card"><h3>Avg Cost/Unit</h3><div class="number">{df["unitCost"].mean():,.0f}</div></div>', unsafe_allow_html=True)

    st.write("") # Spacer

    # KPI Row 2 (Risk Projections)
    k5, k6 = st.columns(2)
    with k5:
        st.markdown(f'<div class="card red"><h3>3 Months Projection (Expiry Value)</h3><div class="number">{exp_3m["Total Value"].sum()/1e9:.2f}B</div></div>', unsafe_allow_html=True)
    with k6:
        st.markdown(f'<div class="card red"><h3>6 Months Projection (Expiry Value)</h3><div class="number">{exp_6m["Total Value"].sum()/1e9:.2f}B</div></div>', unsafe_allow_html=True)

    st.divider()

    # --- 6. BRANCH ANALYSIS (Matching HTML expanders) ---
    st.subheader("📋 Branch Inventory (3-Month Risk Analysis)")
    
    plants = sorted(df['Plant'].unique())
    for plant in plants:
        plant_data = exp_3m[exp_3m['Plant'] == plant].sort_values('Total Value', ascending=False)
        
        if not plant_data.empty:
            with st.expander(f"Plant: {int(plant)} | Risk Items Found"):
                # Clean up display
                display_df = plant_data[['Material', 'Description', 'Expiry', 'Units', 'Total Value']].copy()
                display_df['Expiry'] = display_df['Expiry'].dt.strftime('%d-%b-%Y')
                
                # Format numbers for the table
                st.table(display_df.style.format({
                    'Units': '{:,.0f}',
                    'Total Value': '{:,.0f}'
                }))
        else:
            st.caption(f"Plant {int(plant)}: No 3-month expiry risk detected.")

else:
    st.warning("⚠️ Data file not found. Please trigger the 'Nightly API Sync' in GitHub Actions to generate the dashboard data.")
    st.info("The first sync usually takes 5-10 minutes to process the API items.")

# --- 7. SIDEBAR CONTROLS ---
with st.sidebar:
    st.header("Dashboard Settings")
    if st.button("🔄 Check for New Data"):
        st.rerun()
    
    if os.path.exists(DATA_FILE):
        sync_time = datetime.fromtimestamp(os.path.getmtime(DATA_FILE)).strftime('%Y-%m-%d %H:%M:%S')
        st.write(f"**Last Sync:** {sync_time}")
