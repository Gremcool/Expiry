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
        if res.status_code == 200:
            return res.json().get("token")
        log(f"❌ AUTH ERROR: Status {res.status_code} - Check your credentials in GitHub Secrets.")
    except Exception as e:
        log(f"❌ AUTH CONNECTION ERROR: {e}")
    return None

def fetch_master_data(token):
    mat_lookup = {}
    branch_lookup = {}
    
    # 1. MATERIALS API: Just for Product Descriptions
    headers = {"Authorization": f"Bearer {token}"}
    try:
        log("📡 Requesting Materials Master for descriptions...")
        res = requests.get(MATERIALS_URL, headers=headers, timeout=30)
        if res.status_code == 200:
            items = res.json().get("items", [])
            for m in items:
                h = m.get("header", {})
                mid = str(h.get("Material"))
                if mid:
                    mat_lookup[mid] = h.get("Material Description", "N/A")
            log(f"✅ MATERIALS SUCCESS: Loaded {len(mat_lookup)} descriptions.")
        else:
            log(f"❌ MATERIALS API ERROR: Status {res.status_code}. Using GRN fallback names.")
    except Exception as e:
        log(f"❌ MATERIALS CONNECTION ERROR: {e}")

    # 2. BRANCH CSV: Just for Plant-to-Name Mapping
    try:
        if os.path.exists("Branch.csv"):
            branch_df = pd.read_csv("Branch.csv")
            # Map 'Plant' ID column to 'Branch' Name column
            if 'Plant' in branch_df.columns and 'Branch' in branch_df.columns:
                branch_lookup = dict(zip(branch_df['Plant'].astype(str), branch_df['Branch']))
                log(f"✅ BRANCH CSV SUCCESS: Loaded {len(branch_lookup)} plant mappings.")
            else:
                log(f"❌ BRANCH CSV FORMAT ERROR: Missing 'Plant' or 'Branch' columns. Found: {list(branch_df.columns)}")
        else:
            log("❌ BRANCH CSV MISSING: 'Branch.csv' not found in repo root.")
    except Exception as e:
        log(f"❌ BRANCH CSV READ ERROR: {e}")

    return mat_lookup, branch_lookup

def fetch_item_details(doc_id, token):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(f"{BASE_URL}/{doc_id}", headers=headers, timeout=15)
        return r.json() if r.status_code == 200 else None
    except:
        return None

def run_sync():
    log("🚀 Starting Data Sync...")
    token = get_token()
    if not token: return
    
    mat_lookup, branch_lookup = fetch_master_data(token)

    # 3. GRN API: Get the documents
    headers = {"Authorization": f"Bearer {token}"}
    try:
        res = requests.get(BASE_URL, headers=headers, timeout=30)
        docs = res.json().get("items", [])[:800] 
        doc_ids = [d.get("materialDocument") for d in docs if d.get("materialDocument")]
        log(f"📡 GRN LIST SUCCESS: Found {len(doc_ids)} documents to process.")
    except Exception as e:
        log(f"❌ GRN LIST ERROR: {e}")
        return

    all_rows = []
    with ThreadPoolExecutor(max_workers=30) as executor:
        results = list(executor.map(lambda x: fetch_item_details(x, token), doc_ids))
    
    log("🔄 Finalizing Data Extraction...")
    for entry in results:
        if not entry or "header" not in entry: continue
        h = entry.get("header")
        
        # Filter for medicines
        if h.get("Material Type") != "ZMED": continue

        mat_id = str(h.get("Material"))
        plant_id = str(h.get("Plant"))
        
        all_rows.append({
            "Material": mat_id,
            "Description": mat_lookup.get(mat_id, h.get("Material Description", "N/A")),
            "Units": float(h.get("Quantity", 0)),
            "Plant": plant_id,
            # MAP PLANT ID TO BRANCH NAME
            "Branch": branch_lookup.get(plant_id, f"Unmapped Plant {plant_id}"),
            "Expiry": h.get("SLED/BBD"),
            "Batch": h.get("Batch", "N/A"),
            "Program": h.get("WBS Element") or h.get("WBS Element.1", "General"),
            "Total Value": float(h.get("Amt.in Loc.Cur.", 0))
        })
    
    if all_rows:
        pd.DataFrame(all_rows).to_csv("expiry_data.csv", index=False)
        log(f"🎉 SUCCESS! {len(all_rows)} ZMED items saved.")
    else:
        log("⚠️ SYNC COMPLETE: But zero ZMED items were found in this batch.")

if __name__ == "__main__":
    run_sync()
