import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
import os

# API Config
BASE_URL = "http://197.243.27.208:9097/api/dataservices/grn"
AUTH_URL = "http://197.243.27.208:9097/api/auth/validate"

def get_token():
    user = os.getenv("API_USER")
    pw = os.getenv("API_PASS")
    print(f"🔑 Logging in as {user}...")
    try:
        # Added a strict timeout so it doesn't hang here
        res = requests.post(AUTH_URL, json={"username": user, "password": pw}, timeout=15)
        if res.status_code == 200:
            print("✅ Token obtained.")
            return res.json().get("token")
        print(f"❌ Login Error {res.status_code}: {res.text}")
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
    return None

def fetch_item(doc_id, token):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        # STRICT 10s TIMEOUT: If the API is too slow, skip it rather than hanging
        r = requests.get(f"{BASE_URL}/{doc_id}", headers=headers, timeout=10)
        return r.json() if r.status_code == 200 else None
    except:
        return None

def run_sync():
    print("🚀 Starting High-Speed Data Sync...")
    token = get_token()
    if not token: return

    headers = {"Authorization": f"Bearer {token}"}
    try:
        print("📡 Fetching GRN list...")
        res = requests.get(BASE_URL, headers=headers, timeout=20)
        docs = res.json().get("items", [])
        doc_ids = [d.get("materialDocument") for d in docs if d.get("materialDocument")]
        print(f"📦 Found {len(doc_ids)} documents.")
    except Exception as e:
        print(f"❌ Could not get list: {e}")
        return

    # INCREASED TO 30 WORKERS FOR SPEED
    all_rows = []
    print(f"⚡ Processing {len(doc_ids)} items using 30 parallel workers...")
    with ThreadPoolExecutor(max_workers=30) as executor:
        results = list(executor.map(lambda x: fetch_item(x, token), doc_ids))
    
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
        print(f"✅ SUCCESS! Saved {len(df)} rows to expiry_data.csv")
    else:
        print("⚠️ No data was collected.")

if __name__ == "__main__":
    run_sync()
