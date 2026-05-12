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

def fetch_material_names(token):
    headers = {"Authorization": f"Bearer {token}"}
    lookup = {}
    try:
        log("📡 Fetching Material Names...")
        res = requests.get(MATERIALS_URL, headers=headers, timeout=30)
        if res.status_code == 200:
            for m in res.json().get("items", []):
                h = m.get("header", {})
                mid = str(h.get("Material"))
                if mid: lookup[mid] = h.get("Material Description")
    except: log("⚠️ Material lookup failed, using fallback names.")
    return lookup

def fetch_item_details(doc_id, token):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(f"{BASE_URL}/{doc_id}", headers=headers, timeout=15)
        return r.json() if r.status_code == 200 else None
    except: return None

def run_sync():
    log("🚀 Starting Minimalist Sync...")
    token = get_token()
    if not token: 
        log("❌ Auth Failed")
        return
    
    mat_lookup = fetch_material_names(token)

    try:
        res = requests.get(BASE_URL, headers={"Authorization": f"Bearer {token}"}, timeout=30)
        # We take a small batch (500) to ensure success
        docs = res.json().get("items", [])[:500] 
        doc_ids = [d.get("materialDocument") for d in docs if d.get("materialDocument")]
        log(f"📡 Processing {len(doc_ids)} documents...")
    except: return

    all_rows = []
    with ThreadPoolExecutor(max_workers=30) as executor:
        results = list(executor.map(lambda x: fetch_item_details(x, token), doc_ids))
    
    for entry in results:
        if not entry or "header" not in entry: continue
        h = entry.get("header")
        
        # Only medicine
        if h.get("Material Type") == "ZMED":
            mid = str(h.get("Material"))
            all_rows.append({
                "Material": mid,
                "Description": mat_lookup.get(mid, h.get("Material Description", "N/A")),
                "Units": float(h.get("Quantity", 0)),
                "Plant": h.get("Plant"),
                "Branch": f"Plant {h.get('Plant')}", # Fallback since we are skipping CSV
                "Expiry": h.get("SLED/BBD"),
                "Batch": h.get("Batch", "N/A"),
                "Program": h.get("WBS Element") or h.get("WBS Element.1", "General"),
                "Total Value": float(h.get("Amt.in Loc.Cur.", 0))
            })
    
    if all_rows:
        pd.DataFrame(all_rows).to_csv("expiry_data.csv", index=False)
        log(f"🎉 SUCCESS! {len(all_rows)} items saved.")
    else:
        log("⚠️ No ZMED items found in this batch.")

if __name__ == "__main__":
    run_sync()
