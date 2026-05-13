import requests
import json
import os
import pandas as pd

# API Configuration
GRN_URL = "http://197.243.27.208:9097/api/dataservices/grn"
MATERIALS_URL = "http://197.243.27.208:9097/api/dataservices/materials"
AUTH_URL = "http://197.243.27.208:9097/api/auth/validate"

def log(message):
    print(message, flush=True)

def get_token():
    user = os.getenv("API_USER")
    pw = os.getenv("API_PASS")
    try:
        res = requests.post(AUTH_URL, json={"username": user, "password": pw}, timeout=20)
        return res.json().get("token") if res.status_code == 200 else None
    except Exception as e:
        log(f"❌ Auth Error: {e}")
        return None

def dump_data(url, filename, token, key_name="items"):
    """Generic function to fetch API data and save as JSON."""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        log(f"📡 Fetching {filename}...")
        # Using size=15000 to capture full datasets
        res = requests.get(f"{url}?size=15000", headers=headers, timeout=60)
        if res.status_code == 200:
            data = res.json()
            
            os.makedirs('data', exist_ok=True)
            with open(f'data/{filename}', 'w') as f:
                json.dump(data, f, indent=4)
            log(f"✅ Saved: data/{filename}")
            return True
    except Exception as e:
        log(f"⚠️ Error dumping {filename}: {e}")
    return False

def run_sync():
    log("🚀 Starting Triple-Dump Sync for Dashboard...")
    token = get_token()
    if not token:
        log("❌ Critical: Could not authenticate.")
        return

    # 1. Dump GRN Data (The 'items' from your earlier screenshots)
    dump_data(GRN_URL, "raw_grn.json", token, key_name="items")

    # 2. Dump Materials Master (The 'data' from your earlier screenshots)
    dump_data(MATERIALS_URL, "raw_materials.json", token, key_name="data")

    # 3. Check for Branch.csv
    if os.path.exists("Branch.csv"):
        log("✅ Branch.csv detected for dashboard joining.")
    else:
        log("⚠️ Warning: Branch.csv not found in root directory.")

if __name__ == "__main__":
    run_sync()
