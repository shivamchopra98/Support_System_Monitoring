import os
import re
import json
import socket
import platform
import psutil
import requests
import getpass
from datetime import datetime

import boto3

# AWS Bedrock client
bedrock = boto3.client(service_name="bedrock-runtime", region_name="us-east-1")

TICKET_FILE = "tickets.json"


# -------------------------------------------------------------
# 1) 🔢 Generate Incremental Ticket ID
# -------------------------------------------------------------
def generate_ticket_id():
    if os.path.exists(TICKET_FILE) and os.path.getsize(TICKET_FILE) > 0:
        try:
            with open(TICKET_FILE, "r", encoding="utf-8") as file:
                tickets = json.load(file)

            # Find last valid ticket ID
            for t in reversed(tickets):
                if re.match(r"INC\d{7}$", t["ticket_id"]):
                    last_num = int(t["ticket_id"][3:])
                    return f"INC{last_num + 1:07d}"

        except (json.JSONDecodeError, ValueError):
            pass

    return "INC0000001"


# -------------------------------------------------------------
# 2) 🧠 Summarize Issue (Claude)
# -------------------------------------------------------------
def summarize_issue(user_text):
    try:
        model_id = "anthropic.claude-3-sonnet-20240229-v1:0"

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 80,
            "system": "Summarize the user issue into a short technical problem title.",
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": user_text}]}
            ]
        })

        response = bedrock.invoke_model(modelId=model_id, body=body)
        result = json.loads(response["body"].read())

        return result["content"][0]["text"].strip()

    except Exception:
        return user_text[:80]


# -------------------------------------------------------------
# 3) 🎯 Classify Category (Claude)
# -------------------------------------------------------------
def classify_ticket(issue_text):
    try:
        model_id = "anthropic.claude-3-sonnet-20240229-v1:0"

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 30,
            "system":
                "You are an IT service desk assistant. "
                "Classify the issue into EXACTLY one of these categories: "
                "Network Issue, Hardware Issue, Software Issue, Authentication Issue, "
                "Performance Issue, General Support. Return ONLY the category name.",
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": issue_text}]}
            ]
        })

        response = bedrock.invoke_model(modelId=model_id, body=body)
        raw_output = json.loads(response["body"].read())["content"][0]["text"].strip()

        valid = [
            "Network Issue", "Hardware Issue", "Software Issue",
            "Authentication Issue", "Performance Issue", "General Support"
        ]
        for v in valid:
            if v.lower() in raw_output.lower():
                return v

        return "General Support"

    except Exception:
        return "General Support"


# -------------------------------------------------------------
# 4) 🌍 Detect User Location (IP-based)
# -------------------------------------------------------------
def get_user_location():
    """
    Multi-provider lookup for stable user location.
    Always returns a readable city/region/country.
    """

    def fetch_json(url):
        try:
            return requests.get(url, timeout=5).json()
        except Exception:
            return None

    # ---------------------------
    # 1) Try ipify (IPv4 only)
    # ---------------------------
    try:
        ip_data = fetch_json("https://api.ipify.org?format=json")
        ip = ip_data.get("ip") if ip_data else None
    except Exception:
        ip = None

    # If still no IP, try 2nd provider
    if not ip:
        try:
            ipv4 = fetch_json("https://ipv4.icanhazip.com")
            if ipv4:
                ip = ipv4.strip()
        except Exception:
            ip = None

    # If still no IP — last fallback
    if not ip:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = None

    # ---------------------------
    # 2) Try geolocation providers
    # ---------------------------
    providers = [
        f"https://ipapi.co/{ip}/json/" if ip else None,
        f"https://ipinfo.io/{ip}/json" if ip else None,
        "https://ipwho.is/",
    ]

    location = None
    for url in providers:
        if not url:
            continue
        data = fetch_json(url)
        if not data:
            continue

        # Unified fields from different providers
        location = (
            data.get("city")
            or data.get("region")
            or data.get("country")
            or data.get("country_name")
            or data.get("location", {}).get("city")
            or None
        )

        if location:
            break

    return location or "Unknown"


# -------------------------------------------------------------
# 5) 💻 Collect Device Information
# -------------------------------------------------------------
def collect_device_info():
    try:
        return {
            "os": platform.system(),
            "os_version": platform.version(),
            "processor": platform.processor(),
            "cpu_count": psutil.cpu_count(logical=True),
            "ram_gb": round(psutil.virtual_memory().total / (1024**3), 2),
            "disk": {p.mountpoint: psutil.disk_usage(p.mountpoint)._asdict()
                     for p in psutil.disk_partitions()},
            "ip_address": socket.gethostbyname(socket.gethostname()),
            "hostname": socket.gethostname()
        }
    except Exception as e:
        return {"error": str(e)}


# -------------------------------------------------------------
# 6) 💾 Save Ticket
# -------------------------------------------------------------
def save_ticket(user_text):
    ticket_id = generate_ticket_id()
    username = getpass.getuser().capitalize()
    hostname = socket.gethostname()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    location = get_user_location()
    device_info = collect_device_info()

    summarized_issue = summarize_issue(user_text)
    category = classify_ticket(summarized_issue)

    # Convert device info dict → pretty JSON string (fixes [object Object])
    device_info_str = json.dumps(device_info, indent=2)

    new_ticket = {
        "ticket_id": ticket_id,
        "username": username,
        "issue": summarized_issue,
        "category": category,
        "status": "unresolved",
        "assigned_to": "L1",
        "hostname": hostname,
        "location": location,
        "timestamp": timestamp,
        "device_info": device_info_str   # 🔥 FIXED!
    }

    # Load / append
    tickets = []
    if os.path.exists(TICKET_FILE) and os.path.getsize(TICKET_FILE) > 0:
        try:
            with open(TICKET_FILE, "r") as f:
                tickets = json.load(f)
        except json.JSONDecodeError:
            tickets = []

    tickets.append(new_ticket)

    with open(TICKET_FILE, "w") as f:
        json.dump(tickets, f, indent=4)

    return new_ticket


# -------------------------------------------------------------
# 7) Manual Testing
# -------------------------------------------------------------
if __name__ == "__main__":
    while True:
        issue = input("Describe your issue: ")
        if issue.lower() == "exit":
            break
        t = save_ticket(issue)
        print("\nCreated ticket:", t)
