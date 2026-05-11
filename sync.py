import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
import os
import sys

# API Config
BASE_URL = "http://197.243.27.208:9097/api/dataservices/grn"
AUTH_URL = "http://197.243.27.208:9097/api/auth/validate"

def log(message):
    """Helper to force logs to show up in GitHub immediately"""
    print(message)
    sys.stdout.flush()

def get_token():
    user = os.getenv("API_USER")
    pw = os.getenv("API_PASS")
    log(f"🔑 Attempting login for: {user}...")
    
    try:
        res = requests.post(AUTH_URL, json={"username": user, "password": pw}, timeout=20)
        if res.status_code == 200:
            log("✅ Login Successful! Token obtained.")
            return res.json().get("token")
        log(f"❌ Login Failed ({res.status_code}): {res.text}")
    except Exception as e:
        log(f"❌ Connection Error: {e}")
    return None

def fetch_item(doc_id, token):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(f"{BASE_URL}/{doc_id}", headers=headers, timeout=15)
        return r.json() if r.status_code == 200 else None
    except:
        return None

def run_sync():
    log("🚀 Starting Aggressive Data Sync...")
    token = get_token()
    if not token:
        log("⛔ Aborting: No valid token.")
        return

    headers = {"Authorization": f"Bearer {token}"}
    try:
        log("📡 Requesting GRN Header List...")
        res = requests.get(BASE_URL, headers=headers, timeout=30)
        docs = res.json().get("items", [])
        doc_ids = [d.get("materialDocument") for d in docs if d.get("materialDocument")]
        log(f"📦 Total Documents Found: {len(doc_ids)}")
    except Exception as e:
        log(f"❌ List Fetch Failed: {e}")
        return

    all_rows = []
    log(f"⚡ Firing 30 parallel workers to fetch details...")
    
    # Using 30 workers to finish quickly
    with ThreadPoolExecutor(max_workers=30) as executor:
        results = list(executor.map(lambda x: fetch_item(x, token), doc_ids))
    
    log("🔄 Processing results into table format...")
    for data in results:
        if data:
            items = data if isinstance(data, list) else [data]
            for i in items:
                all_rows.append({
                    "Material": i.get("material"),
                    "Description": i.get("materialName"),
                    "Units": float(i.get("quantity", 0)),
                    "Plant": i.get("plant"),
                    "Expiry": i.get("expiryDate"),
                    "unitCost": float(i.get("unitCost", 0))
                })
    
    if all_rows:
        df = pd.DataFrame(all_rows)
        df.to_csv("expiry_data.csv", index=False)
        log(f"🎉 SUCCESS! {len(df)} rows saved to expiry_data.csv")
    else:
        log("⚠️ Sync finished, but no data was found.")

if __name__ == "__main__":
    run_sync()
