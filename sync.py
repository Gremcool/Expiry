import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
import os

# API Config
BASE_URL = "http://197.243.27.208:9097/api/dataservices/grn"
AUTH_URL = "http://197.243.27.208:9097/api/auth/validate"

def get_token():
    # In GitHub Actions, we use environment variables for security
    user = os.getenv("API_USER")
    pw = os.getenv("API_PASS")
    res = requests.post(AUTH_URL, json={"username": user, "password": pw}, timeout=20)
    return res.json().get("token")

def fetch_item(doc_id, token):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(f"{BASE_URL}/{doc_id}", headers=headers, timeout=20)
        return r.json() if r.status_code == 200 else None
    except: return None

def run_sync():
    print("🚀 Starting Data Sync...")
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Get All Headers
    res = requests.get(BASE_URL, headers=headers, timeout=30)
    docs = res.json().get("items", [])
    doc_ids = [d.get("materialDocument") for d in docs if d.get("materialDocument")]
    
    # 2. Parallel Fetch (Processing the "Suffering" in background)
    all_rows = []
    with ThreadPoolExecutor(max_workers=10) as executor:
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
                    "Expiry": i.get("expiryDate"), # Save as string for CSV
                    "unitCost": float(i.get("unitCost", 0))
                })
    
    df = pd.DataFrame(all_rows)
    df.to_csv("expiry_data.csv", index=False)
    print(f"✅ Sync Complete. Saved {len(df)} rows to expiry_data.csv")

if __name__ == "__main__":
    run_sync()
