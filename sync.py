import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
import os
import sys

# API Config
BASE_URL = "http://197.243.27.208:9097/api/dataservices/grn"
AUTH_URL = "http://197.243.27.208:9097/api/auth/validate"

def log(message):
    """Force logs to show up in GitHub Actions immediately."""
    print(message, flush=True)

def get_token():
    user = os.getenv("API_USER")
    pw = os.getenv("API_PASS")
    log(f"🔑 Attempting login for user: {user}...")
    try:
        res = requests.post(AUTH_URL, json={"username": user, "password": pw}, timeout=20)
        if res.status_code == 200:
            log("✅ Login Successful! Token obtained.")
            return res.json().get("token")
        log(f"❌ Login Failed ({res.status_code}): {res.text}")
    except Exception as e:
        log(f"❌ Connection Error during login: {e}")
    return None

def fetch_item(doc_id, token):
    """Fetch detail for a single document."""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        # 10s timeout ensures one slow item doesn't hang the whole sync
        r = requests.get(f"{BASE_URL}/{doc_id}", headers=headers, timeout=10)
        return r.json() if r.status_code == 200 else None
    except:
        return None

def run_sync():
    log("🚀 Starting Aggressive Data Sync...")
    token = get_token()
    if not token:
        log("⛔ Aborting: Could not obtain auth token.")
        return

    headers = {"Authorization": f"Bearer {token}"}
    try:
        log("📡 Requesting GRN Header List...")
        res = requests.get(BASE_URL, headers=headers, timeout=30)
        all_docs = res.json().get("items", [])
        total_count = len(all_docs)
        log(f"📦 Total documents on server: {total_count}")

        # --- SELECTION LOGIC ---
        # We only take the first 500 to ensure the script finishes in ~5 minutes
        sync_docs = all_docs[:500] 
        log(f"⚡ Syncing the latest {len(sync_docs)} documents to stay within time limits...")
        
        doc_ids = [d.get("materialDocument") for d in sync_docs if d.get("materialDocument")]
    except Exception as e:
        log(f"❌ Failed to fetch list: {e}")
        return

    all_rows = []
    log(f"Firing 30 parallel workers to fetch details for {len(doc_ids)} items...")
    
    # Process documents in parallel
    with ThreadPoolExecutor(max_workers=30) as executor:
        results = list(executor.map(lambda x: fetch_item(x, token), doc_ids))
    
    log("🔄 Processing results into table format...")
    for data in results:
        if data:
            items = data if isinstance(data, list) else [data]
            for i in items:
                # Mapping specifically to the fields needed for your dashboard
                all_rows.append({
                    "Material": i.get("material"),
                    "Description": i.get("materialName", "N/A"),
                    "Units": float(i.get("quantity", 0)),
                    "Plant": i.get("plant"),
                    "Expiry": i.get("expiryDate"),
                    "unitCost": float(i.get("unitCost", 0))
                })
    
    if all_rows:
        df = pd.DataFrame(all_rows)
        # Overwrite the CSV file in the repository
        df.to_csv("expiry_data.csv", index=False)
        log(f"🎉 SUCCESS! {len(df)} rows saved to expiry_data.csv")
    else:
        log("⚠️ Sync finished, but no valid item data was found.")

if __name__ == "__main__":
    run_sync()
