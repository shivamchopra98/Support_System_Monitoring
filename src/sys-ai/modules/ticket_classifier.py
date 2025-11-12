import os
import re
import json
import boto3
import getpass

# AWS Bedrock client
bedrock = boto3.client(service_name="bedrock-runtime", region_name="us-east-1")

TICKET_FILE = "tickets.json"


# ---------------------------------------------------------------------
# 🧩 Utility - Generate Incremental Ticket ID
# ---------------------------------------------------------------------
def generate_ticket_id():
    if os.path.exists(TICKET_FILE) and os.path.getsize(TICKET_FILE) > 0:
        try:
            with open(TICKET_FILE, "r", encoding="utf-8") as file:
                tickets = json.load(file)
            last_ticket = next(
                (t for t in reversed(tickets) if re.match(r"INC\d{7}$", t["ticket_id"])),
                None,
            )
            if last_ticket:
                last_num = int(last_ticket["ticket_id"][3:])
                return f"INC{last_num + 1:07d}"
        except (json.JSONDecodeError, ValueError):
            pass
    return "INC0000001"


# ---------------------------------------------------------------------
# 🧠 Summarize User Issue using Claude 3
# ---------------------------------------------------------------------
def summarize_issue(user_text):
    """
    Converts a user-provided message into a short, descriptive issue title.
    Example: "My laptop is freezing and browsers not opening" -> "Laptop freezing and browsers unresponsive"
    """
    try:
        model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 100,
            "system": (
                "You are an IT service assistant. Summarize the issue described by the user "
                "into a short and clear technical problem statement, without greetings or extra text."
            ),
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": user_text}]
                }
            ]
        })
        response = bedrock.invoke_model(modelId=model_id, body=body)
        result = json.loads(response["body"].read())
        return result["content"][0]["text"].strip()
    except Exception as e:
        print(f"⚠️ Error summarizing issue: {e}")
        return user_text[:80]  # fallback short version


# ---------------------------------------------------------------------
# 🧩 Classify Issue into a Category (via Claude)
# ---------------------------------------------------------------------
def classify_ticket(issue_text):
    """
    Dynamically classifies the user's issue into one IT category.
    The model is instructed to return ONLY the exact category name.
    """
    try:
        model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 30,
            "system": (
                "You are an IT service desk assistant. "
                "Classify the following issue into ONE of these exact categories: "
                "Network Issue, Hardware Issue, Software Issue, Authentication Issue, Performance Issue, or General Support. "
                "Return ONLY the category name — no explanations, no sentences."
            ),
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": issue_text}]
                }
            ]
        })

        response = bedrock.invoke_model(modelId=model_id, body=body)
        result = json.loads(response["body"].read())

        # Extract model output safely
        raw_output = result.get("content", [{}])[0].get("text", "").strip()

        # Normalize the output (in case Claude adds extra words)
        valid_categories = [
            "Network Issue",
            "Hardware Issue",
            "Software Issue",
            "Authentication Issue",
            "Performance Issue",
            "General Support"
        ]
        for cat in valid_categories:
            if cat.lower() in raw_output.lower():
                return cat

        # 🟡 Fallback to Claude’s raw text (sometimes it's perfect)
        if len(raw_output.split()) <= 4:
            return raw_output

        # Default fallback
        return "General Support"

    except Exception as e:
        print(f"⚠️ Error classifying issue: {e}")
        return "General Support"

# ---------------------------------------------------------------------
# 💾 Save Ticket to JSON
# ---------------------------------------------------------------------
def save_ticket(user_text):
    """Creates and saves a new ticket with summarized issue & category."""
    ticket_id = generate_ticket_id()
    username = getpass.getuser().capitalize()  # Get system username (e.g., ShivamChopra)
    summarized_issue = summarize_issue(user_text)
    category = classify_ticket(summarized_issue)

    new_ticket = {
        "ticket_id": ticket_id,
        "username": username,
        "issue": summarized_issue,
        "category": category,
        "status": "unresolved",
        "assigned_to": "L1"
    }

    tickets = []
    if os.path.exists(TICKET_FILE) and os.path.getsize(TICKET_FILE) > 0:
        try:
            with open(TICKET_FILE, "r", encoding="utf-8") as file:
                tickets = json.load(file)
        except json.JSONDecodeError:
            tickets = []

    tickets.append(new_ticket)

    with open(TICKET_FILE, "w", encoding="utf-8") as file:
        json.dump(tickets, file, indent=4)

    return new_ticket


# ---------------------------------------------------------------------
# 🔍 Manual Test
# ---------------------------------------------------------------------
if __name__ == "__main__":
    while True:
        issue = input("\nDescribe your issue (or 'exit'): ")
        if issue.lower() == "exit":
            break
        ticket = save_ticket(issue)
        print(f"\n✅ Ticket Created: {ticket['ticket_id']}")
        print(f"📝 Issue: {ticket['issue']}")
        print(f"📂 Category: {ticket['category']}")
        print(f"👨‍💻 Assigned to: {ticket['assigned_to']}")
