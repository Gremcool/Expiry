import requests
import json
import os

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
    except: return None

def dump_data(url, filename, token):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        log(f"📡 Fetching {filename}...")
        # Get full dataset
        res = requests.get(f"{url}?size=15000", headers=headers, timeout=60)
        if res.status_code == 200:
            raw_json = res.json()
            
            # Determine list location: GRN uses 'items', Materials uses 'data'
            is_materials = "materials" in url
            records = raw_json.get("data" if is_materials else "items", [])

            processed = []
            for item in records:
                # 1. Start with the top-level fields (materialDocument, entryDate, etc.)
                # 2. Merge it with everything inside the 'header' block (Material, Batch, Plant)
                header_data = item.get("header", {})
                
                # Combine them into one flat object
                flat_record = {**item, **header_data}
                
                # Remove the nested 'header' key from the final output to keep it clean
                if "header" in flat_record:
                    del flat_record["header"]
                
                processed.append(flat_record)

            # Save as JSON
            os.makedirs('data', exist_ok=True)
            with open(f'data/{filename}', 'w') as f:
                json.dump(processed, f, indent=4)
            log(f"✅ Saved {len(processed)} records to data/{filename}")
    except Exception as e:
        log(f"⚠️ Error: {e}")

def run_sync():
    log("🚀 Starting Raw Data Dumps...")
    token = get_token()
    if not token: 
        log("❌ Auth failed.")
        return

    # Dump 1: Raw GRN data (Now includes Material and Batch from the header)
    dump_data(GRN_URL, "raw_grn.json", token)
    
    # Dump 2: Raw Materials Master data
    dump_data(MATERIALS_URL, "raw_materials.json", token)

if __name__ == "__main__":
    run_sync()
