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

def fetch_master_lookups(token):
    """Fetches Material names from API and Branch names from CSV."""
    headers = {"Authorization": f"Bearer {token}"}
    mat_lookup = {}
    branch_lookup = {}

    # 1. Materials API
    try:
        res = requests.get(MATERIALS_URL, headers=headers, timeout=30)
        if res.status_code == 200:
            for m in res.json().get("items", []):
                h = m.get("header", {})
                mid = str(h.get("Material"))
                if mid: mat_lookup[mid] = h.get("Material Description")
            log(f"✅ Loaded {len(mat_lookup)} material descriptions.")
    except: log("⚠️ Material lookup API failed.")

    # 2. Branch CSV (SAFE LOAD)
    try:
        if os.path.exists("Branch.csv"):
            branch_df = pd.read_csv("Branch.csv")
            # Convert to string to ensure IDs match API format
            branch_lookup = dict(zip(branch_df['Plant'].astype(str), branch_df['Branch']))
            log(f"✅ Successfully mapped {len(branch_lookup)} branches from CSV.")
        else:
            log("ℹ️ Branch.csv not found. Using Plant IDs as labels.")
    except Exception as e:
        log(f"⚠️ Branch mapping skipped due to error: {e}")

    return mat_lookup, branch_lookup

def fetch_item_details(doc_id, token):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(f"{BASE_URL}/{doc_id}", headers=headers, timeout=15)
        return r.json() if r.status_code == 200 else None
    except: return None

def run_sync():
    log("🚀 Starting Sync (with Branch Mapping)...")
    token = get_token()
    if not token: return
    
    mat_lookup, branch_lookup = fetch_master_lookups(token)

    try:
        res = requests.get(BASE_URL, headers={"Authorization": f"Bearer {token}"}, timeout=30)
        docs = res.json().get("items", [])[:800] 
        doc_ids = [d.get("materialDocument") for d in docs if d.get("materialDocument")]
        log(f"📡 Processing {len(doc_ids)} documents...")
    except: return

    all_rows = []
    with ThreadPoolExecutor(max_workers=30) as executor:
        results = list(executor.map(lambda x: fetch_item_details(x, token), doc_ids))
    
    for entry in results:
        if not entry or "header" not in entry: continue
        h = entry.get("header")
        
        if h.get("Material Type") == "ZMED":
            mid = str(h.get("Material"))
            pid = str(h.get("Plant"))
            
            all_rows.append({
                "Material": mid,
                "Description": mat_lookup.get(mid, h.get("Material Description", "N/A")),
                "Units": float(h.get("Quantity", 0)),
                "Plant": pid,
                # Try to get Branch name, fallback to 'Plant XXX' if not in CSV
                "Branch": branch_lookup.get(pid, f"Plant {pid}"), 
                "Expiry": h.get("SLED/BBD"),
                "Batch": h.get("Batch", "N/A"),
                "Program": h.get("WBS Element") or h.get("WBS Element.1", "General"),
                "Total Value": float(h.get("Amt.in Loc.Cur.", 0))
            })
    
    if all_rows:
        pd.DataFrame(all_rows).to_csv("expiry_data.csv", index=False)
        log(f"🎉 SUCCESS! {len(all_rows)} items saved.")
    else:
        log("⚠️ No ZMED items found.")

if __name__ == "__main__":
    run_sync()
