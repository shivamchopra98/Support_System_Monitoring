# modules/chat_support.py
import json
import os
import time
from typing import List, Dict, Any

CHAT_FILE = "chat_messages.json"


def initialize_chat_file():
    """Create the chat file if it doesn't exist."""
    if not os.path.exists(CHAT_FILE):
        with open(CHAT_FILE, "w") as f:
            json.dump([], f, indent=4)


def load_chat() -> List[Dict[str, Any]]:
    """Return list of all chat messages."""
    initialize_chat_file()
    try:
        with open(CHAT_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []


def save_chat(messages: List[Dict[str, Any]]):
    """Overwrite chat file with messages."""
    with open(CHAT_FILE, "w") as f:
        json.dump(messages, f, indent=4)


def add_message(user: str, role: str, message: str):
    """
    Append a new message.
    - user: username or identifier (e.g., 'shivam' or 'it_team' for IT messages)
    - role: 'user' or 'it'
    - message: text of the message
    """
    messages = load_chat()
    messages.append({
        "user": user,
        "role": role,
        "message": message,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    })
    save_chat(messages)


def get_chat_for_user(username: str) -> List[Dict[str, Any]]:
    """
    Return messages visible to a given user.
    We consider messages where `user` equals username (user messages)
    or messages with role == 'it' and user == username (IT replies are saved with user field pointing to the user).
    """
    messages = load_chat()
    # We store IT replies with the 'user' field set to the target username.
    return [m for m in messages if m.get("user") == username]


def get_active_users() -> List[str]:
    """Return a list of unique users who have sent messages (role == 'user')."""
    messages = load_chat()
    users = {m["user"] for m in messages if m.get("role") == "user"}
    return sorted(list(users))
