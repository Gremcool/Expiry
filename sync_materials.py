import requests
import json
import base64
import os
from datetime import datetime

# --- API CONFIGURATION ---
# These must be set in your GitHub Repo Secrets
BASE_URL = "http://197.243.27.208:9097"
USERNAME = os.getenv("API_USERNAME")
PASSWORD = os.getenv("API_PASSWORD")

# --- GITHUB AUTO-CONFIGURATION ---
# GitHub Actions provides these automatically
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_PATH = os.getenv("GITHUB_REPOSITORY")  # Format: "owner/repo"
FILE_PATH = "data/material_master.json"
BRANCH = "main"

def get_bearer_token():
    print("Authenticating with API...")
    payload = {"username": USERNAME, "password": PASSWORD}
    response = requests.post(f"{BASE_URL}/api/auth/validate", json=payload)
    response.raise_for_status()
    return response.json().get("token")

def fetch_materials(token):
    print("Fetching materials list...")
    headers = {"Authorization": f"Bearer {token}"}
    # Using size=20000 to ensure we get all ~10k records in one go
    params = {"page": 0, "size": 20000}
    response = requests.get(f"{BASE_URL}/api/dataservices/materials", headers=headers, params=params)
    response.raise_for_status()
    return response.json()

def sync_to_github(data):
    print(f"Syncing data to {REPO_PATH}...")
    url = f"https://api.github.com/repos/{REPO_PATH}/contents/{FILE_PATH}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    # Get the file's current state to find the 'sha' (required for updates)
    current_file = requests.get(url, headers=headers)
    sha = current_file.json().get("sha") if current_file.status_code == 200 else None

    # Prepare JSON content
    content_str = json.dumps(data, indent=4)
    content_encoded = base64.b64encode(content_str.encode()).decode()

    payload = {
        "message": f"Nightly Material Sync: {datetime.now().strftime('%Y-%m-%d')}",
        "content": content_encoded,
        "branch": BRANCH
    }
    if sha:
        payload["sha"] = sha

    # Put the file back into the repo
    response = requests.put(url, headers=headers, json=payload)
    if response.status_code in [200, 201]:
        print("Success: Material master updated in GitHub.")
    else:
        print(f"Error: {response.status_code} - {response.text}")

if __name__ == "__main__":
    # Check if we have the critical API credentials
    if not USERNAME or not PASSWORD:
        print("Critical Error: API_USERNAME or API_PASSWORD not found in environment.")
    elif not GITHUB_TOKEN:
        print("Critical Error: GITHUB_TOKEN not found (Check your Workflow YAML).")
    else:
        try:
            token = get_bearer_token()
            materials = fetch_materials(token)
            sync_to_github(materials)
        except Exception as e:
            print(f"Sync failed: {e}")
