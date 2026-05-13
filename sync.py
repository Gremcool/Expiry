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
    except: 
        return None

def dump_data(url, filename, token):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        log(f"📡 Fetching data for {filename}...")
        res = requests.get(f"{url}?size=15000", headers=headers, timeout=60)
        if res.status_code == 200:
            raw_json = res.json()
            is_materials = "materials" in url
            records = raw_json.get("data" if is_materials else "items", [])

            flattened_results = []
            for item in records:
                header_content = item.get("header", {})
                # This merges the nested Material and Batch into the top level
                flat_row = {**item, **header_content}
                if "header" in flat_row:
                    del flat_row["header"]
                flattened_results.append(flat_row)

            os.makedirs('data', exist_ok=True)
            with open(f'data/{filename}', 'w') as f:
                json.dump(flattened_results, f, indent=4)
            log(f"✅ Saved {len(flattened_results)} records to data/{filename}")
    except Exception as e:
        log(f"⚠️ Error: {e}")

def run_sync():
    log("🚀 Starting Raw Data Dumps...")
    token = get_token()
    if not token: 
        log("❌ Authentication failed. Check API_USER and API_PASS secrets.")
        return

    dump_data(GRN_URL, "raw_grn.json", token)
    dump_data(MATERIALS_URL, "raw_materials.json", token)

if __name__ == "__main__":
    run_sync()
