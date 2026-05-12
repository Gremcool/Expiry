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
    """Authenticates and retrieves the Bearer token."""
    user = os.getenv("API_USER")
    pw = os.getenv("API_PASS")
    try:
        log(f"🔑 Attempting login for user: {user}...")
        res = requests.post(AUTH_URL, json={"username": user, "password": pw}, timeout=20)
        if res.status_code == 200:
            log("✅ Login successful.")
            return res.json().get("token")
        log(f"❌ Login failed: {res.status_code}")
    except Exception as e:
        log(f"❌ Connection error during login: {e}")
    return None

def fetch_master_lookups(token):
    """Fetches and maps Material names and Branch names."""
    headers = {"Authorization": f"Bearer {token}"}
    mat_lookup = {}
    branch_lookup = {}

    # 1. Materials API (Handling lowercase keys: materialId, materialDescription)
    try:
        log("📡 Fetching Material Master descriptions...")
        res = requests.get(MATERIALS_URL, headers=headers, timeout=30)
        if res.status_code == 200:
            items = res.json().get("items", [])
            for m in items:
                h = m.get("header", {})
                mid = str(h.get("materialId")) # Precise lowercase key
                mdesc = h.get("materialDescription") # Precise lowercase key
                if mid and mdesc:
                    mat_lookup[mid] = mdesc
            log(f"✅ MATERIALS: {len(mat_lookup)} names loaded.")
        else:
            log(f"⚠️ MATERIALS API FAILED: Status {res.status_code}")
    except Exception as e:
        log(f"⚠️ MATERIALS API ERROR: {e}")

    # 2. Branch CSV (Mapping Plant to Branch name)
    try:
        if os.path.exists("Branch.csv"):
            branch_df = pd.read_csv("Branch.csv")
            # Clean column names in case of hidden spaces
            branch_df.columns = [c.strip() for c in branch_df.columns]
            
            if 'Plant' in branch_df.columns and 'Branch' in branch_df.columns:
                branch_lookup = dict(zip(branch_df['Plant'].astype(str), branch_df['Branch']))
                log(f"✅ BRANCH CSV: {len(branch_lookup)} mappings loaded.")
            else:
                log(f"❌ BRANCH CSV ERROR: Columns 'Plant' or 'Branch' not found.")
        else:
            log("ℹ️ Branch.csv not found in repository.")
    except Exception as e:
        log(f"⚠️ Branch mapping error: {e}")

    return mat_lookup, branch_lookup

def fetch_item_details(doc_id, token):
    """Fetches details for a single GRN document."""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(f"{BASE_URL}/{doc_id}", headers=headers, timeout=15)
        return r.json() if r.status_code == 200 else None
    except:
        return None

def run_sync():
    log("🚀 Starting Targeted Data Sync...")
    token = get_token()
    if not token: return
    
    # Load metadata
    mat_lookup, branch_lookup = fetch_master_lookups(token)

    # Fetch main GRN list
    headers = {"Authorization": f"Bearer {token}"}
    try:
        res = requests.get(BASE_URL, headers=headers, timeout=30)
        docs = res.json().get("items", [])[:800] 
        doc_ids = [d.get("materialDocument") for d in docs if d.get("materialDocument")]
        log(f"📡 Found {len(doc_ids)} documents. Syncing details...")
    except Exception as e:
        log(f"❌ GRN List fetch failed: {e}")
        return

    all_rows = []
    # Parallel fetching for speed
    with ThreadPoolExecutor(max_workers=30) as executor:
        results = list(executor.map(lambda x: fetch_item_details(x, token), doc_ids))
    
    log("🔄 Finalizing data extraction and filtering (ZMED)...")
    for entry in results:
        if not entry or "header" not in entry: continue
        h = entry.get("header")
        
        # FILTER: Only Medicines
        if h.get("Material Type") == "ZMED":
            grn_mat_id = str(h.get("Material")) # Capitalized in GRN API
            plant_id = str(h.get("Plant"))
            
            all_rows.append({
                "Material": grn_mat_id,
                # Lookup maps GRN's 'Material' to Material API's 'materialId'
                "Description": mat_lookup.get(grn_mat_id, h.get("Material Description", "N/A")),
                "Units": float(h.get("Quantity", 0)),
                "Plant": plant_id,
                "Branch": branch_lookup.get(plant_id, f"Plant {plant_id}"),
                "Expiry": h.get("SLED/BBD"),
                "Batch": h.get("Batch", "N/A"),
                "Program": h.get("WBS Element") or h.get("WBS Element.1", "General"),
                "Total Value": float(h.get("Amt.in Loc.Cur.", 0))
            })
    
    if all_rows:
        pd.DataFrame(all_rows).to_csv("expiry_data.csv", index=False)
        log(f"🎉 SUCCESS! {len(all_rows)} ZMED items saved.")
    else:
        log("⚠️ SYNC FINISHED: No ZMED items found in this batch.")

if __name__ == "__main__":
    run_sync()
