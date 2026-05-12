import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
import os
import sys

# API Configuration
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

def fetch_master_lookups(token):
    """Maps materialId to Description and Type from Materials Master."""
    headers = {"Authorization": f"Bearer {token}"}
    mat_lookup = {}
    
    try:
        log("📡 Fetching Material Master for descriptions and types...")
        res = requests.get(MATERIALS_URL, headers=headers, timeout=30)
        if res.status_code == 200:
            items = res.json().get("items", [])
            for m in items:
                h = m.get("header", {})
                mid = str(h.get("materialId")) # From 1st Pic
                if mid:
                    mat_lookup[mid] = {
                        "name": h.get("materialDescription", "N/A"),
                        "type": h.get("materialType", "N/A")
                    }
            log(f"✅ MATERIALS: {len(mat_lookup)} products mapped.")
    except Exception as e:
        log(f"⚠️ Materials Master error: {e}")

    # Branch mapping logic
    branch_lookup = {}
    try:
        if os.path.exists("Branch.csv"):
            branch_df = pd.read_csv("Branch.csv")
            branch_lookup = dict(zip(branch_df['Plant'].astype(str), branch_df['Branch']))
    except: pass

    return mat_lookup, branch_lookup

def fetch_item_details(doc_id, token):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(f"{BASE_URL}/{doc_id}", headers=headers, timeout=15)
        return r.json() if r.status_code == 200 else None
    except: return None

def run_sync():
    log("🚀 Starting Precise Mapping Sync...")
    token = get_token()
    if not token: return
    
    mat_info, branch_lookup = fetch_master_lookups(token)

    headers = {"Authorization": f"Bearer {token}"}
    try:
        res = requests.get(BASE_URL, headers=headers, timeout=30)
        docs = res.json().get("items", [])[:800] 
        doc_ids = [d.get("materialDocument") for d in docs if d.get("materialDocument")]
    except: return

    all_rows = []
    with ThreadPoolExecutor(max_workers=30) as executor:
        results = list(executor.map(lambda x: fetch_item_details(x, token), doc_ids))
    
    for entry in results:
        if not entry or "header" not in entry: continue
        h = entry.get("header")
        
        # MAPPING: Match 'Material' from GRN (2nd Pic) to 'materialId' from Materials (1st Pic)
        grn_mat_id = str(h.get("Material"))
        
        # Get data from our lookup table
        master_data = mat_info.get(grn_mat_id, {})
        m_type = master_data.get("type", h.get("Material Type")) # Fallback to GRN type
        
        # FILTER: Process if type is ZMED
        if m_type == "ZMED":
            all_rows.append({
                "Material": grn_mat_id,
                "Description": master_data.get("name", h.get("Material Description", "N/A")),
                "MaterialType": m_type,
                "Units": float(h.get("Quantity", 0)),
                "Plant": h.get("Plant"),
                "Branch": branch_lookup.get(str(h.get("Plant")), f"Plant {h.get('Plant')}"),
                "Expiry": h.get("SLED/BBD"),
                "Batch": h.get("Batch", "N/A"),
                "Program": h.get("WBS Element") or h.get("WBS Element.1", "General"),
                "Total Value": float(h.get("Amt.in Loc.Cur.", 0))
            })
    
    if all_rows:
        pd.DataFrame(all_rows).to_csv("expiry_data.csv", index=False)
        log(f"🎉 SUCCESS! {len(all_rows)} ZMED items synced with descriptions.")

if __name__ == "__main__":
    run_sync()
