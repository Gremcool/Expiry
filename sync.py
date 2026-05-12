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
        log(f"❌ AUTH ERROR: Status {res.status_code}")
    except Exception as e:
        log(f"❌ AUTH CONNECTION ERROR: {e}")
    return None

def fetch_material_lookup(token):
    """Only fetches medicine names from the Materials API."""
    headers = {"Authorization": f"Bearer {token}"}
    lookup = {}
    try:
        log("📡 Fetching Material descriptions...")
        res = requests.get(MATERIALS_URL, headers=headers, timeout=30)
        if res.status_code == 200:
            items = res.json().get("items", [])
            for m in items:
                h = m.get("header", {})
                mid = str(h.get("Material"))
                if mid:
                    lookup[mid] = h.get("Material Description", "N/A")
            log(f"✅ MATERIALS: {len(lookup)} descriptions loaded.")
    except:
        log("⚠️ Materials lookup failed.")
    return lookup

def fetch_item_details(doc_id, token):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(f"{BASE_URL}/{doc_id}", headers=headers, timeout=15)
        return r.json() if r.status_code == 200 else None
    except:
        return None

def run_sync():
    log("🚀 Starting Data Sync (CSV Ignored)...")
    token = get_token()
    if not token: return
    
    # Notice: We only expect ONE variable now (mat_lookup)
    mat_lookup = fetch_material_lookup(token)

    headers = {"Authorization": f"Bearer {token}"}
    try:
        res = requests.get(BASE_URL, headers=headers, timeout=30)
        docs = res.json().get("items", [])[:800] 
        doc_ids = [d.get("materialDocument") for d in docs if d.get("materialDocument")]
        log(f"📡 Found {len(doc_ids)} docs. Syncing...")
    except:
        return

    all_rows = []
    with ThreadPoolExecutor(max_workers=30) as executor:
        results = list(executor.map(lambda x: fetch_item_details(x, token), doc_ids))
    
    for entry in results:
        if not entry or "header" not in entry: continue
        h = entry.get("header")
        
        # Filter for medicines only
        if h.get("Material Type") == "ZMED":
            mid = str(h.get("Material"))
            all_rows.append({
                "Material": mid,
                "Description": mat_lookup.get(mid, h.get("Material Description", "N/A")),
                "Units": float(h.get("Quantity", 0)),
                "Plant": h.get("Plant"),
                "Expiry": h.get("SLED/BBD"),
                "Batch": h.get("Batch", "N/A"),
                "Program": h.get("WBS Element") or h.get("WBS Element.1", "General"),
                "Total Value": float(h.get("Amt.in Loc.Cur.", 0))
            })
    
    if all_rows:
        pd.DataFrame(all_rows).to_csv("expiry_data.csv", index=False)
        log(f"🎉 SUCCESS! {len(all_rows)} ZMED items saved.")
    else:
        log("⚠️ Sync complete, but no ZMED items found.")

if __name__ == "__main__":
    run_sync()
