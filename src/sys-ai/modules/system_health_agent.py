import psutil
import time
import json
import boto3
import datetime
import os
from modules.ticket_classifier import save_ticket  # Reuse your ticket system

# AWS Bedrock client
bedrock = boto3.client(service_name="bedrock-runtime", region_name="us-east-1")

HEALTH_LOG_FILE = "system_health_log.json"


def get_system_metrics():
    """Collects system health metrics (CPU, RAM, Disk)."""
    cpu_usage = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    metrics = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cpu_usage": cpu_usage,
        "ram_usage": ram.percent,
        "disk_usage": disk.percent,
    }
    return metrics


def analyze_with_bedrock(metrics):
    """Analyzes metrics using AWS Bedrock (Claude 3 Sonnet) and gives suggestions."""
    try:
        model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
        user_prompt = (
            f"System Metrics:\n"
            f"- CPU Usage: {metrics['cpu_usage']}%\n"
            f"- RAM Usage: {metrics['ram_usage']}%\n"
            f"- Disk Usage: {metrics['disk_usage']}%\n\n"
            "Analyze the system health and provide a short summary. "
            "If there is a problem (usage above 85%), include exact actions the IT team should take. "
            "Otherwise, respond with 'System operating normally.'"
        )

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 250,
            "system": (
                "You are a proactive IT system monitoring assistant. "
                "Your job is to detect abnormal system usage and suggest quick fixes "
                "such as restarting services, freeing memory, or cleaning disk space."
            ),
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": user_prompt}]
                }
            ]
        })

        response = bedrock.invoke_model(modelId=model_id, body=body)
        result = json.loads(response["body"].read())
        suggestion = result["content"][0]["text"].strip()
        return suggestion

    except Exception as e:
        return f"⚠️ Error analyzing metrics: {e}"


def is_critical(metrics):
    """Determines if any metric is in a critical state."""
    return (
        metrics["cpu_usage"] > 90
        or metrics["ram_usage"] > 90
        or metrics["disk_usage"] > 95
    )


def log_health_data(metrics, suggestion):
    """Saves scan results locally."""
    entry = {
        "timestamp": metrics["timestamp"],
        "cpu_usage": metrics["cpu_usage"],
        "ram_usage": metrics["ram_usage"],
        "disk_usage": metrics["disk_usage"],
        "suggestion": suggestion,
    }

    # Load existing data
    data = []
    if os.path.exists(HEALTH_LOG_FILE):
        try:
            with open(HEALTH_LOG_FILE, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            data = []

    data.append(entry)
    with open(HEALTH_LOG_FILE, "w") as f:
        json.dump(data, f, indent=4)


def run_health_scan():
    """Runs one scan, logs it, analyzes with AI, and creates a ticket if needed."""
    metrics = get_system_metrics()
    print(f"📊 Metrics Collected: {metrics}")

    suggestion = analyze_with_bedrock(metrics)
    print(f"🧠 AI Suggestion: {suggestion}")

    log_health_data(metrics, suggestion)

    # 🚨 Auto-create ticket if system in critical condition
    if is_critical(metrics):
        issue_desc = (
            f"Critical System Health Alert: CPU {metrics['cpu_usage']}%, "
            f"RAM {metrics['ram_usage']}%, Disk {metrics['disk_usage']}%. "
            f"AI Suggestion: {suggestion}"
        )
        ticket = save_ticket(issue_desc)
        print(f"🎟️ Auto Ticket Created: {ticket['ticket_id']} | {ticket['category']}")
        return metrics, suggestion, ticket

    return metrics, suggestion, None


def start_auto_agent(interval_minutes=5):
    """Continuously runs scans every N minutes."""
    print("🚀 System Health Agent started.")
    while True:
        metrics, suggestion, ticket = run_health_scan()

        print("\n=== SCAN COMPLETE ===")
        print(f"🕒 Time: {metrics['timestamp']}")
        print(f"💾 CPU: {metrics['cpu_usage']}% | RAM: {metrics['ram_usage']}% | Disk: {metrics['disk_usage']}%")
        print(f"💡 Suggestion: {suggestion}")
        if ticket:
            print(f"🎫 Ticket Raised: {ticket['ticket_id']} ({ticket['category']})\n")

        time.sleep(interval_minutes * 60)


# Manual run test
if __name__ == "__main__":
    start_auto_agent(interval_minutes=2)
