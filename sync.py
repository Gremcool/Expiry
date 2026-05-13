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
    except Exception as e:
        log(f"❌ Auth Error: {e}")
        return None

def clean_id(val):
    """Numerical conversion to fix the 'extra zeros' issue for later joining."""
    if val is None: return ""
    s_val = str(val).strip()
    try:
        return str(int(s_val))
    except ValueError:
        return s_val.lstrip('0')

def dump_data(url, filename, token):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        log(f"📡 Fetching data for {filename}...")
        res = requests.get(f"{url}?size=15000", headers=headers, timeout=60)
        if res.status_code == 200:
            raw_json = res.json()
            
            is_materials = "materials" in url
            records = raw_json.get("data" if is_materials else "items", [])

            processed = []
            for item in records:
                # 1. Get the header block where the real data lives
                header = item.get("header", {})
                
                # 2. Create a flat record for this item
                # We start with the header data (Material Document, Plant, etc.)
                record = header.copy()
                
                if is_materials:
                    # Materials Master Logic
                    mid = header.get("materialId")
                    record["join_id"] = clean_id(mid)
                else:
                    # GRN Logic: Explicitly capture Material and Batch from the header
                    # Use the exact keys seen in your Postman screenshot
                    record["Material"] = header.get("Material")
                    record["Batch"] = header.get("Batch")
                    record["join_id"] = clean_id(header.get("Material"))

                processed.append(record)

            os.makedirs('data', exist_ok=True)
            with open(f'data/{filename}', 'w') as f:
                json.dump(processed, f, indent=4)
            log(f"✅ Saved {len(processed)} records to data/{filename}")
            return True
    except Exception as e:
        log(f"⚠️ Error processing {filename}: {e}")
    return False

def run_sync():
    log("🚀 Starting Separate Dumps...")
    token = get_token()
    if not token: return

    # Dump 1: Raw GRN data (includes Material, Batch, etc.)
    dump_data(GRN_URL, "raw_grn.json", token)
    
    # Dump 2: Raw Materials Master data
    dump_data(MATERIALS_URL, "raw_materials.json", token)

if __name__ == "__main__":
    run_sync()
