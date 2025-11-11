import json
import os
import re
import boto3
import json

TICKET_FILE = "tickets.json"

# Initialize AWS Bedrock client
bedrock = boto3.client(service_name="bedrock-runtime", region_name="us-east-1")

def generate_ticket_id():
    """Generates an auto-incrementing ticket ID in the format INC0000001."""
    if os.path.exists(TICKET_FILE) and os.path.getsize(TICKET_FILE) > 0:
        try:
            with open(TICKET_FILE, "r", encoding="utf-8") as file:
                tickets = json.load(file)

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

def classify_ticket(issue):
    """Classifies IT issues using AWS Bedrock (Claude 3 Sonnet)."""
    try:
        model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 128,
            "messages": [
                {
                    "role": "user",
                    "content": f"Classify this IT support issue into a category (Network, Hardware, Software, Authentication, Email, or General): {issue}"
                }
            ]
        })

        response = bedrock.invoke_model(modelId=model_id, body=body)
        result = json.loads(response["body"].read())
        category = result["content"][0]["text"].strip()
        return category
    except Exception as e:
        print(f"Error classifying ticket: {e}")
        return "General Support"

def save_ticket(issue):
    """Creates and saves a new ticket."""
    ticket_id = generate_ticket_id()
    category = classify_ticket(issue)
    new_ticket = {
        "ticket_id": ticket_id,
        "username": "Ram",
        "issue": issue,
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

if __name__ == "__main__":
    print("💬 Ticket Classifier Test (Bedrock Edition)\n")
    while True:
        issue_description = input("Enter an issue: ")
        if issue_description.lower() == "exit":
            break
        ticket = save_ticket(issue_description)
        print(f"\n✅ Ticket {ticket['ticket_id']} created in category: {ticket['category']}\n")
