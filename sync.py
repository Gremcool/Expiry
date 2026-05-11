import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
import os
import sys

# API Config
BASE_URL = "http://197.243.27.208:9097/api/dataservices/grn"
AUTH_URL = "http://197.243.27.208:9097/api/auth/validate"

def log(message):
    print(message, flush=True)

def get_token():
    user = os.getenv("API_USER")
    pw = os.getenv("API_PASS")
    log(f"🔑 Logging in as {user}...")
    try:
        res = requests.post(AUTH_URL, json={"username": user, "password": pw}, timeout=20)
        if res.status_code == 200:
            return res.json().get("token")
        log(f"❌ Login failed: {res.status_code}")
    except Exception as e:
        log(f"❌ Connection error: {e}")
    return None

def fetch_item(doc_id, token):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(f"{BASE_URL}/{doc_id}", headers=headers, timeout=15)
        if r.status_code == 200:
            return r.json()
    except:
        return None
    return None

def run_sync():
    log("🚀 Starting Data Sync...")
    token = get_token()
    if not token: return

    headers = {"Authorization": f"Bearer {token}"}
    try:
        res = requests.get(BASE_URL, headers=headers, timeout=30)
        # Taking latest 500 to keep it fast
        docs = res.json().get("items", [])[:500] 
        doc_ids = [d.get("materialDocument") for d in docs if d.get("materialDocument")]
        log(f"📦 Syncing {len(doc_ids)} latest documents...")
    except Exception as e:
        log(f"❌ List fetch failed: {e}")
        return

    all_rows = []
    with ThreadPoolExecutor(max_workers=30) as executor:
        results = list(executor.map(lambda x: fetch_item(x, token), doc_ids))
    
    log("🔄 Extracting item data from nested 'header' structure...")
    for entry in results:
        if not entry or "header" not in entry:
            continue
        
        # Based on your screenshot, data is inside the 'header' key
        h = entry.get("header")
        
        # Map exact keys from your screenshot to your dashboard criteria
        all_rows.append({
            "Material": h.get("Material"),
            "Description": h.get("Material Description", "N/A"),
            "Units": float(h.get("Quantity", 0)),
            "Plant": h.get("Plant"),
            "Expiry": h.get("Expiry Date"),
            "unitCost": float(h.get("Unit Cost", 0)),
            "DocNumber": h.get("Material Document")
        })
    
    if all_rows:
        df = pd.DataFrame(all_rows)
        # This overwrites the CSV in your GitHub repo for Streamlit to read
        df.to_csv("expiry_data.csv", index=False)
        log(f"✅ SUCCESS! Saved {len(df)} rows to expiry_data.csv")
    else:
        log("⚠️ No data was extracted. Check if 'header' key exists in API response.")

if __name__ == "__main__":
    run_sync()
