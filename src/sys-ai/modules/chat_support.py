import json
import os
import time
from typing import List, Dict, Any

CHAT_FILE = "chat_messages.json"

def initialize_chat_file():
    if not os.path.exists(CHAT_FILE):
        with open(CHAT_FILE, "w") as f:
            json.dump([], f, indent=4)

def load_chat() -> List[Dict[str, Any]]:
    initialize_chat_file()
    try:
        with open(CHAT_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []

def save_chat(messages: List[Dict[str, Any]]):
    with open(CHAT_FILE, "w") as f:
        json.dump(messages, f, indent=4)

def add_message(user: str, role: str, message: str):
    messages = load_chat()
    messages.append({
        "user": user,
        "role": role,
        "message": message,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    })
    save_chat(messages)

def get_chat_for_user(username: str) -> List[Dict[str, Any]]:
    messages = load_chat()
    return [m for m in messages if m.get("user") == username]

def get_active_users() -> List[str]:
    messages = load_chat()
    users = {m["user"] for m in messages if m.get("role") == "user"}
    return sorted(list(users))
