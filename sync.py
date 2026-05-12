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

def fetch_material_master(token):
    """Fetch all materials to create a lookup table for descriptions."""
    headers = {"Authorization": f"Bearer {token}"}
    log("📦 Fetching Material Master for descriptions...")
    try:
        res = requests.get(MATERIALS_URL, headers=headers, timeout=30)
        if res.status_code == 200:
            # Create a dictionary {materialID: description}
            # Adjust the keys 'materialID' and 'description' if your API uses different names
            materials = res.json().get("items", [])
            lookup = {str(m.get("materialID")): m.get("materialName") or m.get("description") for m in materials}
            log(f"✅ Loaded {len(lookup)} material descriptions.")
            return lookup
    except Exception as e:
        log(f"⚠️ Could not load material descriptions: {e}")
    return {}

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
    log("🚀 Starting Data Sync with Material Mapping...")
    token = get_token()
    if not token: return

    # 1. Get Material Metadata first
    material_lookup = fetch_material_master(token)

    # 2. Get GRN Headers
    headers = {"Authorization": f"Bearer {token}"}
    try:
        res = requests.get(BASE_URL, headers=headers, timeout=30)
        docs = res.json().get("items", [])[:500] 
        doc_ids = [d.get("materialDocument") for d in docs if d.get("materialDocument")]
        log(f"📡 Syncing {len(doc_ids)} GRN documents...")
    except Exception as e:
        log(f"❌ GRN List fetch failed: {e}")
        return

    # 3. Fetch Items in Parallel
    all_rows = []
    with ThreadPoolExecutor(max_workers=30) as executor:
        results = list(executor.map(lambda x: fetch_item(x, token), doc_ids))
    
    log("🔄 Mapping descriptions and extracting data...")
    for entry in results:
        if not entry or "header" not in entry:
            continue
        
        h = entry.get("header")
        mat_id = str(h.get("Material"))
        
        # Get description from API, if empty try the Master Lookup we just built
        desc = h.get("Material Description")
        if not desc or desc == "N/A":
            desc = material_lookup.get(mat_id, "Description Not Found")

        all_rows.append({
            "Material": mat_id,
            "Description": desc,
            "Units": float(h.get("Quantity", 0)),
            "Plant": h.get("Plant"),
            "Expiry": h.get("Expiry Date"),
            "unitCost": float(h.get("Unit Cost", 0)),
            "DocNumber": h.get("Material Document")
        })
    
    if all_rows:
        df = pd.DataFrame(all_rows)
        df.to_csv("expiry_data.csv", index=False)
        log(f"🎉 SUCCESS! Saved {len(df)} rows with descriptions to expiry_data.csv")
    else:
        log("⚠️ No data was extracted.")

if __name__ == "__main__":
    run_sync()
