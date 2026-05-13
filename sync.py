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
    """
    Converts IDs to integers to ignore any length discrepancies or extra zero-padding.
    Example: '1000000001' and '1000001' remain unique, but '0000100' and '100' will match.
    """
    if val is None: return ""
    s_val = str(val).strip()
    try:
        return str(int(s_val))
    except ValueError:
        return s_val.lstrip('0')

def dump_data(url, filename, token):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        log(f"📡 Fetching {filename}...")
        res = requests.get(f"{url}?size=15000", headers=headers, timeout=60)
        if res.status_code == 200:
            raw_json = res.json()
            
            is_materials = "materials" in url
            records = raw_json.get("data" if is_materials else "items", [])

            processed = []
            for item in records:
                # Extract the 'header' block as our flat record
                row = item.get("header", item)
                
                if is_materials:
                    # Logic for Materials Master
                    if "materialId" in row:
                        row["join_id"] = clean_id(row["materialId"])
                else:
                    # Logic for GRN (transaction data)
                    # Ensuring Batch and Material are present as requested
                    row["Material"] = row.get("Material", "N/A")
                    row["Batch"] = row.get("Batch", "N/A")
                    row["join_id"] = clean_id(row["Material"])

                processed.append(row)

            os.makedirs('data', exist_ok=True)
            with open(f'data/{filename}', 'w') as f:
                json.dump(processed, f, indent=4)
            log(f"✅ Saved {len(processed)} records to data/{filename}")
            return True
    except Exception as e:
        log(f"⚠️ Error in {filename}: {e}")
    return False

def run_sync():
    log("🚀 Starting Sync...")
    token = get_token()
    if not token: return

    # Dump the transaction data (GRN)
    dump_data(GRN_URL, "raw_grn.json", token)
    
    # Dump the lookup data (Materials)
    dump_data(MATERIALS_URL, "raw_materials.json", token)

if __name__ == "__main__":
    run_sync()
