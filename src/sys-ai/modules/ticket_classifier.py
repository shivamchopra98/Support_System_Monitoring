import json
import os
import re
from openai import OpenAI, APIError, RateLimitError, AuthenticationError
from config import OPENAI_API_KEY

# --------------------------------------------
# ⚙️ CONFIGURATION
# --------------------------------------------

TICKET_FILE = "tickets.json"
USE_OPENAI = False  # 🔴 Set to False for offline/local testing
                   # 🟢 Set to True when you have a valid OpenAI API key

# Initialize OpenAI client (only if API mode enabled)
client = None
if USE_OPENAI and OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)


# --------------------------------------------
# 🧩 TICKET ID GENERATOR
# --------------------------------------------
def generate_ticket_id():
    """Generates an auto-incrementing ticket ID in the format INC0000001."""
    if os.path.exists(TICKET_FILE) and os.path.getsize(TICKET_FILE) > 0:
        try:
            with open(TICKET_FILE, "r", encoding="utf-8") as file:
                tickets = json.load(file)

            # Find last valid ticket ID
            last_ticket = next(
                (t for t in reversed(tickets) if re.match(r"INC\d{7}$", t["ticket_id"])),
                None
            )

            if last_ticket:
                last_id_num = int(last_ticket["ticket_id"][3:])
                new_id = f"INC{last_id_num + 1:07d}"
            else:
                new_id = "INC0000001"

        except (json.JSONDecodeError, ValueError):
            new_id = "INC0000001"
    else:
        new_id = "INC0000001"

    return new_id


# --------------------------------------------
# 🧠 ISSUE CLASSIFICATION
# --------------------------------------------
def classify_ticket(issue: str) -> str:
    """
    Classifies an IT issue using OpenAI if available,
    otherwise uses simple keyword-based local logic.
    """

    # 🧩 Offline mode (no API call)
    if not USE_OPENAI or not OPENAI_API_KEY:
        issue_lower = issue.lower()

        if "wifi" in issue_lower or "network" in issue_lower:
            return "Network Issue"
        elif "printer" in issue_lower or "print" in issue_lower:
            return "Hardware Issue"
        elif "install" in issue_lower or "software" in issue_lower:
            return "Software Installation"
        elif "password" in issue_lower or "login" in issue_lower:
            return "Authentication Issue"
        elif "email" in issue_lower or "outlook" in issue_lower:
            return "Email Issue"
        elif "server" in issue_lower or "database" in issue_lower:
            return "Server/Database Issue"
        else:
            return "General Support"

    # 🧠 Online mode (OpenAI API)
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an IT service desk agent. Classify the IT issue into categories like Network, Hardware, Software, Email, etc."},
                {"role": "user", "content": issue}
            ],
        )
        category = response.choices[0].message.content.strip()
        return category

    except RateLimitError:
        return "⚠️ OpenAI rate limit reached. Defaulting to 'General Support'."
    except AuthenticationError:
        return "❌ Invalid API key. Defaulting to 'General Support'."
    except APIError as e:
        return f"⚙️ API error: {str(e)}"
    except Exception as e:
        return f"⚠️ Unexpected error: {str(e)}"


# --------------------------------------------
# 💾 SAVE TICKET
# --------------------------------------------
def save_ticket(issue: str) -> dict:
    """Creates and saves a new ticket in tickets.json."""

    ticket_id = generate_ticket_id()
    category = classify_ticket(issue)

    new_ticket = {
        "ticket_id": ticket_id,
        "username": "Ram",  # Replace with dynamic username later if needed
        "issue": issue,
        "category": category,
        "status": "unresolved",
        "assigned_to": "L1"
    }

    # Load existing tickets
    tickets = []
    if os.path.exists(TICKET_FILE) and os.path.getsize(TICKET_FILE) > 0:
        try:
            with open(TICKET_FILE, "r", encoding="utf-8") as file:
                tickets = json.load(file)
        except json.JSONDecodeError:
            tickets = []

    tickets.append(new_ticket)

    # Save to JSON
    with open(TICKET_FILE, "w", encoding="utf-8") as file:
        json.dump(tickets, file, indent=4)

    return new_ticket


# --------------------------------------------
# 🧪 STANDALONE TESTING
# --------------------------------------------
if __name__ == "__main__":
    print("💬 Ticket Classifier Test (type 'exit' to quit)\n")
    while True:
        issue_description = input("Enter an issue: ")
        if issue_description.lower() == "exit":
            break

        ticket = save_ticket(issue_description)
        print(f"\n✅ New Ticket Created: {ticket['ticket_id']}")
        print(f"📂 Category: {ticket['category']}")
        print(f"📝 Issue: {ticket['issue']}\n")
