import psutil
import shutil
import subprocess
import json
import boto3
from datetime import datetime, timedelta
from modules.system_updates import check_pending_updates

bedrock = boto3.client(service_name="bedrock-runtime", region_name="us-east-1")

#############################################
# 1. AI ANALYZER
#############################################
def ask_ai(summary_text):
    try:
        model_id = "anthropic.claude-3-sonnet-20240229-v1:0"

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 300,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"Analyze this system health summary and provide recommendations:\n\n{summary_text}"}
                    ]
                }
            ]
        })

        response = bedrock.invoke_model(modelId=model_id, body=body)
        output = json.loads(response["body"].read())
        return output["content"][0]["text"]
    except Exception as e:
        return f"⚠️ AI analysis failed: {e}"

#############################################
# 2. PERFORMANCE METRICS
#############################################
def get_system_metrics():
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent
    disk = shutil.disk_usage("C:\\").used * 100 / shutil.disk_usage("C:\\").total

    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cpu_usage": round(cpu, 1),
        "ram_usage": round(ram, 1),
        "disk_usage": round(disk, 1)
    }

#############################################
# 3. EVENT LOG SCAN (CRITICAL ONLY)
#############################################
def get_critical_event_logs():
    try:
        last_24_hours = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")
        ps_script = f"""
        Get-WinEvent -FilterHashtable @{{
            LogName='System';
            Level=1;
            StartTime='{last_24_hours}'
        }} | Select-Object TimeCreated, Id, ProviderName, Message | ConvertTo-Json -Depth 4
        """

        result = subprocess.check_output(["powershell", "-Command", ps_script], text=True)
        logs = json.loads(result) if result.strip() else []

        return logs

    except Exception:
        return []

#############################################
# 4. MAIN HEALTH ANALYSIS
#############################################
def system_health_prediction():
    metrics = get_system_metrics()
    updates = check_pending_updates()
    critical_logs = get_critical_event_logs()

    alerts = []

    # Performance issues
    if metrics["cpu_usage"] > 85:
        alerts.append("High CPU usage")
    if metrics["ram_usage"] > 85:
        alerts.append("High RAM usage")
    if metrics["disk_usage"] > 90:
        alerts.append("Critical disk usage")

    # Windows Update
    if updates["pending_updates"]:
        alerts.append("Pending Windows updates available")
    if updates["reboot_required"]:
        alerts.append("Reboot required to finish updates")

    # Event Viewer
    if len(critical_logs) > 0:
        alerts.append(f"{len(critical_logs)} Critical Windows Event Logs detected")

    combined = {
        "metrics": metrics,
        "updates": updates,
        "critical_event_logs": critical_logs[:10],  # show only first 10
        "alerts": alerts
    }

    ai_summary = ask_ai(json.dumps(combined, indent=2))

    return combined, ai_summary
