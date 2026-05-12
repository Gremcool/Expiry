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
    try:
        res = requests.post(AUTH_URL, json={"username": user, "password": pw}, timeout=20)
        return res.json().get("token") if res.status_code == 200 else None
    except: return None

def fetch_master_data(token):
    headers = {"Authorization": f"Bearer {token}"}
    mat_lookup = {}
    try:
        res = requests.get(MATERIALS_URL, headers=headers, timeout=30)
        if res.status_code == 200:
            materials = res.json().get("items", [])
            # Map materialID to materialName for the description lookup
            mat_lookup = {str(m.get("materialID")): m.get("materialName") for m in materials}
    except: log("⚠️ Materials lookup failed.")

    branch_lookup = {}
    try:
        if os.path.exists("Branch.csv"):
            branch_df = pd.read_csv("Branch.csv")
            branch_lookup = dict(zip(branch_df['Plant'].astype(str), branch_df['Branch Name']))
    except: log("⚠️ Branch.csv error.")

    return mat_lookup, branch_lookup

def fetch_item(doc_id, token):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(f"{BASE_URL}/{doc_id}", headers=headers, timeout=15)
        return r.json() if r.status_code == 200 else None
    except: return None

def run_sync():
    log("🚀 Starting Targeted Data Sync...")
    token = get_token()
    if not token: return
    mat_lookup, branch_lookup = fetch_master_data(token)

    try:
        res = requests.get(BASE_URL, headers={"Authorization": f"Bearer {token}"}, timeout=30)
        docs = res.json().get("items", [])[:800] # Increased limit slightly
        doc_ids = [d.get("materialDocument") for d in docs if d.get("materialDocument")]
    except: return

    all_rows = []
    with ThreadPoolExecutor(max_workers=30) as executor:
        results = list(executor.map(lambda x: fetch_item(x, token), doc_ids))
    
    for entry in results:
        if not entry or "header" not in entry: continue
        h = entry.get("header")
        
        # --- FILTERS & MAPPINGS ---
        # 1. Only include ZMED materials
        if h.get("Material Type") != "ZMED":
            continue

        mat_id = str(h.get("Material"))
        plant_id = str(h.get("Plant"))
        
        all_rows.append({
            "Material": mat_id,
            "Description": mat_lookup.get(mat_id, h.get("Material Description", "N/A")),
            "Units": float(h.get("Quantity", 0)),
            "Plant": plant_id,
            "Branch": branch_lookup.get(plant_id, f"Plant {plant_id}"),
            "Expiry": h.get("SLED/BBD"), # Replaces Expiry
            "Batch": h.get("Batch", "N/A"),
            "Program": h.get("WBS Element") or h.get("WBS Element.1", "General"),
            "Total Value": float(h.get("Amt.in Loc.Cur.", 0)), # Direct Value mapping
            "unitCost": float(h.get("Unit Cost", 0))
        })
    
    if all_rows:
        pd.DataFrame(all_rows).to_csv("expiry_data.csv", index=False)
        log(f"🎉 SUCCESS! Sync completed with {len(all_rows)} ZMED items.")

if __name__ == "__main__":
    run_sync()
