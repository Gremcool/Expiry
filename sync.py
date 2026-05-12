import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
import os
import sys

# API Config
BASE_URL = "http://197.243.27.208:9097/api/dataservices/grn"
MATERIALS_URL = "http://197.243.27.208:9097/api/dataservices/materials"
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

def fetch_master_data(token):
    """Fetch material descriptions and branch mappings."""
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Material Lookup
    mat_lookup = {}
    try:
        res = requests.get(MATERIALS_URL, headers=headers, timeout=30)
        if res.status_code == 200:
            materials = res.json().get("items", [])
            mat_lookup = {str(m.get("materialID")): m.get("materialName") or m.get("description") for m in materials}
            log(f"✅ Loaded {len(mat_lookup)} material descriptions.")
    except: log("⚠️ Material descriptions fetch failed.")

    # 2. Branch Mapping (from your uploaded branch.csv)
    branch_lookup = {}
    try:
        if os.path.exists("branch.csv"):
            branch_df = pd.read_csv("branch.csv")
            # Assumes branch.csv has 'Plant' and 'BranchName' columns
            branch_lookup = dict(zip(branch_df['Plant'].astype(str), branch_df['BranchName']))
            log(f"✅ Loaded {len(branch_lookup)} branch mappings from CSV.")
        else:
            log("⚠️ branch.csv not found in repository.")
    except Exception as e:
        log(f"⚠️ Error loading branch.csv: {e}")

    return mat_lookup, branch_lookup

def fetch_item(doc_id, token):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(f"{BASE_URL}/{doc_id}", headers=headers, timeout=15)
        if r.status_code == 200:
            return r.json()
    except: return None
    return None

def run_sync():
    log("🚀 Starting Data Sync with Branch Mapping...")
    token = get_token()
    if not token: return

    mat_lookup, branch_lookup = fetch_master_data(token)

    headers = {"Authorization": f"Bearer {token}"}
    try:
        res = requests.get(BASE_URL, headers=headers, timeout=30)
        docs = res.json().get("items", [])[:500] 
        doc_ids = [d.get("materialDocument") for d in docs if d.get("materialDocument")]
        log(f"📡 Processing {len(doc_ids)} latest documents...")
    except Exception as e:
        log(f"❌ List fetch failed: {e}")
        return

    all_rows = []
    with ThreadPoolExecutor(max_workers=30) as executor:
        results = list(executor.map(lambda x: fetch_item(x, token), doc_ids))
    
    for entry in results:
        if not entry or "header" not in entry: continue
        h = entry.get("header")
        
        mat_id = str(h.get("Material"))
        plant_id = str(h.get("Plant"))
        
        all_rows.append({
            "Material": mat_id,
            "Description": h.get("Material Description") or mat_lookup.get(mat_id, "N/A"),
            "Units": float(h.get("Quantity", 0)),
            "Plant": plant_id,
            "Branch": branch_lookup.get(plant_id, f"Plant {plant_id}"),
            "Expiry": h.get("Expiry Date"),
            "unitCost": float(h.get("Unit Cost", 0))
        })
    
    if all_rows:
        pd.DataFrame(all_rows).to_csv("expiry_data.csv", index=False)
        log(f"🎉 SUCCESS! Saved to expiry_data.csv")

if __name__ == "__main__":
    run_sync()
