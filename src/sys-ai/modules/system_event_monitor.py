import subprocess
import json
import datetime
import os
from modules.ticket_classifier import save_ticket
import boto3

bedrock = boto3.client(service_name="bedrock-runtime", region_name="us-east-1")


def get_recent_event_logs(max_items=20):
    """
    Fetch only CRITICAL (Level=1) logs from Windows Event Viewer (last 24 hours).
    Returns a list of dicts (possibly empty).
    """
    try:
        # PowerShell command: select minimal fields and convert to JSON.
        # -Depth increased to 6 to avoid nested truncation.
        ps_command = r"""
        $logs = Get-WinEvent -FilterHashtable @{
            LogName = 'System','Application';
            Level = 1;
            StartTime = (Get-Date).AddDays(-1)
        }
        if ($logs) {
            $logs |
            Select-Object TimeCreated, Id, LevelDisplayName, ProviderName, Message |
            Select-Object -First {max_items} |
            ConvertTo-Json -Depth 6
        } else {
            ''  # return empty string if no logs
        }
        """.replace("{max_items}", str(max_items))

        # Use -NoProfile and -NonInteractive for predictable output
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_command],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30
        )

        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()

        # Debugging useful info (you may log these instead of printing)
        if stderr:
            # Powershell may write warnings/errors to stderr — expose for debugging
            print(f"[system_event_monitor] PowerShell stderr: {stderr}")

        if not stdout:
            # No JSON output -> no critical logs
            return []

        # Attempt to parse JSON. ConvertTo-Json returns a JSON array or single object
        parsed = json.loads(stdout)
        # Normalize single object -> list
        if isinstance(parsed, dict):
            return [parsed]
        elif isinstance(parsed, list):
            return parsed
        else:
            # Unexpected type: wrap as string message
            return [{"TimeCreated": str(datetime.datetime.now()), "Id": None, "LevelDisplayName": "Critical", "ProviderName": "Unknown", "Message": str(parsed)}]

    except subprocess.TimeoutExpired:
        print("⚠️ PowerShell command timed out.")
        return []
    except json.JSONDecodeError as jde:
        print(f"⚠️ JSON parse error from PowerShell output: {jde}")
        print("PowerShell stdout (first 1000 chars):")
        print(stdout[:1000])
        return []
    except Exception as e:
        print(f"⚠️ Unexpected error in get_recent_event_logs: {e}")
        return []


def analyze_logs_with_ai(logs, max_entries=5):
    """
    Summarize the provided critical logs using Bedrock (Claude).
    Limit to 'max_entries' to keep payload small.
    """
    try:
        if not logs:
            return "✅ No critical events found in the last 24 hours."

        # Prepare a concise text summary for AI input
        entries = []
        for log in logs[:max_entries]:
            time_created = log.get("TimeCreated")
            # PowerShell timestamp sometimes comes as "/Date(17629...)/" — try to keep raw string
            message = str(log.get("Message", "")).replace("\n", " ").strip()
            provider = log.get("ProviderName", "Unknown")
            level = log.get("LevelDisplayName", "")
            entries.append(f"- [{level}] {provider} @ {time_created}: {message[:300]}")

        logs_text = "\n".join(entries)

        model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 300,
            "system": "You are a system health assistant. Summarize critical Windows event logs and provide short remediation steps.",
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": f"Critical event logs (latest up to {max_entries}):\n{logs_text}"}]}
            ]
        })

        response = bedrock.invoke_model(modelId=model_id, body=body)
        result = json.loads(response["body"].read())

        # Extract text robustly
        content = result.get("content")
        if isinstance(content, list) and len(content) > 0:
            first = content[0]
            if isinstance(first, dict) and "text" in first:
                return first["text"].strip()
            elif isinstance(first, (list, tuple)) and len(first) > 1:
                return str(first[1]).strip()
        elif isinstance(content, dict) and "text" in content:
            return content["text"].strip()
        elif isinstance(content, str):
            return content.strip()

        return "⚠️ No textual analysis returned from Bedrock."

    except Exception as e:
        print(f"⚠️ Error analyzing logs with Bedrock: {e}")
        return f"⚠️ Error analyzing logs with Bedrock: {e}"


def run_event_log_scan():
    """
    Runs the event log scan and raises a single ticket if there are critical events.
    Returns: (logs_list, ai_summary, ticket_or_None)
    """
    logs = get_recent_event_logs(max_items=20)
    if not logs:
        return [], "✅ No critical events in last 24 hours.", None

    summary = analyze_logs_with_ai(logs, max_entries=5)

    # If the AI summary contains words indicating a real problem, raise one consolidated ticket
    summary_lower = summary.lower()
    critical_indicators = ["critical", "failure", "failed", "crash", "data loss", "unable to", "cannot", "kernel panic"]
    if any(word in summary_lower for word in critical_indicators):
        # Build an issue description using top logs and the AI summary
        brief = f"Critical event(s) detected in last 24 hours. Top events:\n"
        for log in logs[:5]:
            brief += f"- {log.get('ProviderName','Unknown')} ({log.get('Id')}): {str(log.get('Message',''))[:200]}\n"
        brief += f"\nAI Summary: {summary}"
        ticket = save_ticket(brief)
        return logs, summary, ticket

    # Not critical enough to auto-ticket
    return logs, summary, None
