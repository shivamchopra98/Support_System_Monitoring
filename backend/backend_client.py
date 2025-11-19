# modules/backend_client.py
import os, requests
BACKEND = os.environ.get("SYS_AI_BACKEND", "http://YOUR_BACKEND_HOST:8000")
API_TOKEN = os.environ.get("SYS_AI_BACKEND_TOKEN", "replace-with-strong-token")
HEADERS = {"Authorization": f"Bearer {API_TOKEN}", "Content-Type": "application/json"}

def list_agents():
    r = requests.get(f"{BACKEND}/api/agents", headers=HEADERS, timeout=10)
    r.raise_for_status()
    return r.json()
