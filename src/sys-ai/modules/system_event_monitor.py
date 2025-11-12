import subprocess
import json
import datetime
from modules.ticket_classifier import save_ticket
import boto3

bedrock = boto3.client(service_name="bedrock-runtime", region_name="us-east-1")

def get_recent_event_logs():
    """
    Fetch only CRITICAL (Level=1) logs from Windows Event Viewer (last 24 hours)
    """
    try:
        # PowerShell command to fetch only Level 1 (Critical)
        ps_command = r"""
        Get-WinEvent -FilterHashtable @{
            LogName='System','Application';
            Level=1;
            StartTime=(Get-Date).AddDays(-1)
        } | Select-Object TimeCreated, Id, LevelDisplayName, ProviderName, Message | ConvertTo-Json
        """

        result = subprocess.run(
            ["powershell", "-Command", ps_command],
            capture_output=True, text=True, encoding="utf-8"
        )

        logs = json.loads(result.stdout)
        if not logs:
            return []
        return logs if isinstance(logs, list) else [logs]

    except Exception as e:
        print(f"⚠️ Error fetching logs: {e}")
        return []


def analyze_logs_with_ai(logs):
    """
    Use AWS Bedrock Claude model to analyze logs and summarize the findings
    """
    try:
        logs_text = "\n".join([
            f"{log['TimeCreated']} - {log['ProviderName']} - {log['LevelDisplayName']} - {log['Message'][:150]}"
            for log in logs[:10]  # limit for efficiency
        ])

        model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 300,
            "system": "You are a system health assistant that analyzes Windows event logs to detect root causes and recommend solutions.",
            "messages": [
                {"role": "user", "content": f"Analyze the following event logs and summarize any critical issues:\n{logs_text}"}
            ]
        })

        response = bedrock.invoke_model(modelId=model_id, body=body)
        result = json.loads(response["body"].read())
        return result["content"][0]["text"].strip()

    except Exception as e:
        return f"⚠️ Error analyzing logs with Bedrock: {e}"


def run_event_log_scan():
    """
    Runs a scan on event logs and raises a ticket if critical issues are detected
    """
    logs = get_recent_event_logs()

    if not logs:
        return None, "✅ No recent critical or error logs detected.", None

    ai_summary = analyze_logs_with_ai(logs)

    # Check if AI found any critical keywords
    if any(word in ai_summary.lower() for word in ["critical", "failure", "crash", "error", "malfunction"]):
        ticket = save_ticket("System event log reports critical issues within last 24 hours.")
        return logs, ai_summary, ticket

    return logs, ai_summary, None
