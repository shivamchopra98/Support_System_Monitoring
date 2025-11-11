import os
import re
import boto3
import json

LOG_FILE = "logs/system.log"
os.makedirs("logs", exist_ok=True)
if not os.path.exists(LOG_FILE):
    open(LOG_FILE, "w").close()

# Create Bedrock client
bedrock = boto3.client(service_name="bedrock-runtime", region_name="us-east-1")

def analyze_log_with_ai(log_entry):
    """Analyze logs using AWS Bedrock Claude."""
    try:
        model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
        prompt = f"Analyze the following system log entry and explain the issue:\n{log_entry}"

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 150,
            "messages": [{"role": "user", "content": prompt}]
        })

        response = bedrock.invoke_model(modelId=model_id, body=body)
        result = json.loads(response["body"].read())
        return result["content"][0]["text"].strip()
    except Exception as e:
        return f"Error analyzing log: {e}"

def monitor_logs():
    """Reads and analyzes logs for errors."""
    detected_logs = []
    with open(LOG_FILE, "r") as file:
        lines = file.readlines()

    for line in lines:
        if re.search(r"error|failed|critical", line, re.IGNORECASE):
            ai_analysis = analyze_log_with_ai(line.strip())
            detected_logs.append((line.strip(), ai_analysis))
            print(f"⚠️ Log Issue: {line.strip()}")
            print(f"🧠 AI Analysis: {ai_analysis}\n")

    return detected_logs

if __name__ == "__main__":
    monitor_logs()
