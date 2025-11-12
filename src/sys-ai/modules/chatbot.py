import boto3
import json
from modules.ticket_classifier import save_ticket

# Initialize AWS Bedrock client
bedrock = boto3.client(service_name="bedrock-runtime", region_name="us-east-1")


# ---------------------------------------------------------------------
# 🧠 Claude Chat Function (Properly Structured)
# ---------------------------------------------------------------------
def chat_with_bedrock(messages):
    """
    Sends messages to AWS Bedrock Claude 3 Sonnet with proper alternation and structure.
    """
    try:
        model_id = "anthropic.claude-3-sonnet-20240229-v1:0"

        # Separate system instruction
        system_instruction = None
        chat_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                system_instruction = msg.get("content")
            else:
                chat_messages.append({
                    "role": msg["role"],
                    "content": [{"type": "text", "text": str(msg["content"])}]
                })

        # ✅ Enforce alternation rule
        fixed_messages = []
        last_role = None
        for m in chat_messages:
            if m["role"] == last_role == "user":
                fixed_messages.append({
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Understood."}]
                })
            fixed_messages.append(m)
            last_role = m["role"]

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "system": system_instruction,
            "max_tokens": 400,
            "messages": fixed_messages
        })

        response = bedrock.invoke_model(modelId=model_id, body=body)
        result = json.loads(response["body"].read())

        # Extract AI text
        content = result.get("content")
        if isinstance(content, list) and len(content) > 0 and "text" in content[0]:
            return content[0]["text"].strip()
        elif isinstance(content, dict) and "text" in content:
            return content["text"].strip()
        elif isinstance(content, str):
            return content.strip()
        return "⚠️ No valid text content returned from Claude."

    except Exception as e:
        return f"⚠️ Error communicating with Bedrock: {e}"


# ---------------------------------------------------------------------
# 💬 Chatbot Logic with Smarter Escalation
# ---------------------------------------------------------------------
def get_chatbot_response(user_query, chat_history):
    """
    Generates Claude 3 chatbot response.
    Only raises a ticket after giving troubleshooting advice first.
    """

    # System instruction — clarified to enforce multi-turn logic
    system_instruction = (
        "You are an IT Support Assistant. "
        "You help users troubleshoot common IT issues (network, hardware, software, login, etc.). "
        "Always provide troubleshooting steps or clarifying questions FIRST. "
        "Only respond with the word 'RAISE_TICKET' if the user explicitly asks for it "
        "or confirms that all troubleshooting failed (e.g., 'it still doesn’t work', 'nothing helped', etc.)."
    )

    messages = [{"role": "system", "content": system_instruction}]
    for role, msg in chat_history:
        if role in ["user", "assistant"]:
            messages.append({"role": role, "content": msg})

    messages.append({"role": "user", "content": user_query})

    bot_reply = chat_with_bedrock(messages)

    # --- Escalation Logic ---
    triggers = [
        "raise a ticket", "create a ticket", "open a ticket",
        "contact admin", "still not working", "not resolved",
        "problem persists", "can't fix", "didn't work"
    ]

    # 🚫 Don’t allow ticket escalation in first interaction
    first_message = len(chat_history) == 0

    if (not first_message) and (
        any(p in user_query.lower() for p in triggers) or "RAISE_TICKET" in bot_reply
    ):
        issue_context = next(
            (msg for role, msg in chat_history if role == "user" and any(
                w in msg.lower() for w in
                ["issue", "error", "problem", "not working", "fail", "disconnect", "crash", "slow"]
            )),
            user_query
        )

        ticket = save_ticket(issue_context)
        bot_reply = (
            f"🧾 A support ticket has been created for you.\n"
            f"🎫 **Ticket ID:** {ticket['ticket_id']}\n"
            f"📂 **Category:** {ticket['category']}\n"
            f"👨‍💻 Assigned to: {ticket['assigned_to']}"
        )

    return bot_reply
