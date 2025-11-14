# chatbot.py
"""
Comprehensive chatbot module for SYS-AI (single-file full version).

Features:
- Intent detection (cleanup, restart service, install app, run health scan, follow-up)
- Safe action executors (restart service, cleanup, install)
- Ticket creation via save_ticket when escalation requested
- Bedrock AI fallback (proper message formatting, no "role alternation" errors)
- Streamlit session_state integration for last action tracking
- CLI interactive mode for testing

Drop this file into your project at src/sys-ai/modules/chatbot.py (or adjust imports).
"""

import os
import re
import json
import time
import ctypes
import shutil
import subprocess
import getpass
from typing import List, Tuple, Optional

# -------------------------
# Project imports (ticket saving / classifier / health scan)
# -------------------------
# These imports assume your project modules are available under modules/
try:
    from modules.ticket_classifier import save_ticket, classify_ticket
except Exception:
    # fallback if module is at project root
    try:
        from ticket_classifier import save_ticket, classify_ticket  # type: ignore
    except Exception:
        # lightweight fallback (won't persist)
        def save_ticket(issue):
            return {"ticket_id": "INC0000000", "category": "General Support", "assigned_to": "L1", "username": getpass.getuser()}

        def classify_ticket(issue):
            return "General Support"

# health scan (optional)
try:
    from modules.proactive_health import system_health_prediction as run_health_scan
except Exception:
    try:
        from modules.system_health_agent import run_health_scan  # type: ignore
    except Exception:
        run_health_scan = None  # ok if absent

# Bedrock (optional)
bedrock_available = False
bedrock_client = None
try:
    import boto3  # boto3 may be used to call AWS Bedrock if configured
    bedrock_client = boto3.client(service_name="bedrock-runtime", region_name="us-east-1")
    bedrock_available = True
except Exception:
    bedrock_client = None
    bedrock_available = False

# Streamlit session state integration (optional)
try:
    import streamlit as st  # type: ignore
    SESSION = st.session_state
except Exception:
    # simple dict fallback for CLI/testing
    if "_chatbot_session_state" not in globals():
        globals()["_chatbot_session_state"] = {}
    SESSION = globals()["_chatbot_session_state"]


# -------------------------
# Utilities & Intent Detection
# -------------------------
def _normalize(text: str) -> str:
    return (text or "").strip().lower()


def detect_greeting(text: str) -> bool:
    t = _normalize(text)
    greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening"]
    return any(t == g or t.startswith(g + " ") or t.startswith(g + "!") for g in greetings)


def detect_cleanup_intent(text: str) -> bool:
    t = _normalize(text)
    return any(k in t for k in ["clear temp", "clear cache", "cleanup", "clean temp", "delete temp", "remove temp"])


def detect_restart_service_intent(text: str) -> Optional[str]:
    t = _normalize(text)
    mapping = {
        "wifi": "WlanSvc",
        "wlan": "WlanSvc",
        "printer": "Spooler",
        "windows update": "wuauserv",
        "dns": "Dnscache",
        "dhcp": "Dhcp",
        "remote desktop": "TermService",
        "sql": "MSSQLSERVER",
        "mysql": "MySQL80",
        "apache": "Apache2.4"
    }
    for k, svc in mapping.items():
        if k in t:
            return svc
    if "restart service" in t or "restart the service" in t:
        return "generic"
    return None


def detect_install_intent(text: str) -> Optional[str]:
    t = _normalize(text)
    # Heuristic: "install notepad" or "install notepad++"
    if t.startswith("install ") or " install " in t:
        m = re.search(r"install\s+([a-z0-9\-\_\. \+]+)", t)
        if m:
            return m.group(1).strip()
        return "unknown"
    return None


def detect_run_scan(text: str) -> bool:
    t = _normalize(text)
    return any(k in t for k in ["run health scan", "run scan", "system scan", "health scan", "diagnostic", "run diagnostic"])


def detect_escalation(text: str) -> bool:
    t = _normalize(text)
    return any(p in t for p in ["still not working", "raise a ticket", "create ticket", "open a ticket", "not resolved", "escalate"])


def detect_followup_why(text: str) -> bool:
    t = _normalize(text)
    return any(w in t for w in ["why", "what happened", "explain", "reason", "why did", "why it failed", "why it failed?"])


# -------------------------
# Cleanup logic (safe)
# -------------------------
def _clean_path(path: Optional[str]) -> Tuple[int, int]:
    removed_files = 0
    removed_bytes = 0
    if not path:
        return removed_files, removed_bytes
    try:
        if not os.path.exists(path):
            return removed_files, removed_bytes
        for root, dirs, files in os.walk(path, topdown=False):
            for f in files:
                try:
                    fp = os.path.join(root, f)
                    size = os.path.getsize(fp)
                    os.remove(fp)
                    removed_files += 1
                    removed_bytes += size
                except Exception:
                    pass
            for d in dirs:
                try:
                    os.rmdir(os.path.join(root, d))
                except Exception:
                    pass
    except Exception:
        pass
    return removed_files, removed_bytes


def empty_recycle_bin() -> bool:
    try:
        ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x00000007)
        return True
    except Exception:
        return False


def perform_cleanup() -> str:
    paths = [
        os.getenv("TEMP"),
        os.getenv("TMP"),
        os.path.expanduser(r"~\AppData\Local\Temp"),
        r"C:\Windows\Temp",
        os.path.expanduser(r"~\AppData\Local\CrashDumps"),
        os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data\Default\Cache"),
        os.path.expanduser(r"~\AppData\Local\Microsoft\Edge\User Data\Default\Cache")
    ]
    total_files = 0
    total_bytes = 0
    for p in paths:
        try:
            fcount, fbytes = _clean_path(p)
            total_files += fcount
            total_bytes += fbytes
        except Exception:
            pass
    recycle_ok = empty_recycle_bin()
    mb = total_bytes / (1024 * 1024) if total_bytes else 0.0
    msg = (
        f"🧹 Cleanup finished: removed {total_files} files (~{mb:.2f} MB).\n"
        f"Locations cleaned: Windows Temp, User Temp, CrashDumps, Chrome & Edge caches.\n"
        f"Recycle Bin: {'Emptied' if recycle_ok else 'Failed/Permission denied'}."
    )
    SESSION["last_action_status"] = msg
    return msg


# -------------------------
# Restart service logic
# -------------------------
def perform_restart_service(service_name: str) -> str:
    if service_name == "generic":
        return "Please specify which service to restart (for example: 'restart Wi-Fi' or 'restart printer')."

    try:
        stop_cmd = ["sc", "stop", service_name]
        start_cmd = ["sc", "start", service_name]

        stop_proc = subprocess.run(stop_cmd, capture_output=True, text=True, timeout=30)
        stop_out = (stop_proc.stdout or "") + (stop_proc.stderr or "")

        time.sleep(1)

        start_proc = subprocess.run(start_cmd, capture_output=True, text=True, timeout=30)
        start_out = (start_proc.stdout or "") + (start_proc.stderr or "")

        status_msg = f"Restart attempt for service '{service_name}':\n\nSTOP output:\n{stop_out.strip()}\n\nSTART output:\n{start_out.strip()}"
        if "Access is denied" in (stop_out + start_out):
            status_msg = f"⚠️ Error restarting {service_name}: Access is denied. Try running the app as Administrator."

        SESSION["last_action_status"] = status_msg
        return status_msg

    except subprocess.TimeoutExpired:
        msg = f"⚠️ Timeout while attempting to restart {service_name}."
        SESSION["last_action_status"] = msg
        return msg
    except Exception as e:
        msg = f"⚠️ Error restarting {service_name}: {e}"
        SESSION["last_action_status"] = msg
        return msg


# attempt elevated launch (UAC) using ShellExecuteW
def _run_elevated(exe_path: str, args: str = "") -> bool:
    try:
        rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe_path, args, None, 1)
        return rc > 32
    except Exception:
        return False


# -------------------------
# Install application logic
# -------------------------
WINDOWS_DOWNLOADS = os.path.join(os.path.expanduser("~"), "downloads")
PROJECT_DOWNLOADS = os.path.join(os.path.dirname(__file__), "downloads")
SEARCH_LOCATIONS = [PROJECT_DOWNLOADS, WINDOWS_DOWNLOADS]


def perform_install_app(app_name: str) -> str:
    try:
        exe_candidates = []
        for folder in SEARCH_LOCATIONS:
            if folder and os.path.exists(folder):
                for f in os.listdir(folder):
                    if f.lower().endswith(".exe"):
                        exe_candidates.append((folder, f))
        if not exe_candidates:
            msg = "No .exe installers found in project downloads or user Downloads."
            SESSION["last_action_status"] = msg
            return msg

        app_norm = (app_name or "").lower()
        chosen_folder, chosen_file = None, None
        if app_norm and app_norm != "unknown":
            for folder, fname in exe_candidates:
                if app_norm in fname.lower() or app_norm.replace(" ", "") in fname.lower():
                    chosen_folder, chosen_file = folder, fname
                    break

        if not chosen_folder:
            chosen_folder, chosen_file = exe_candidates[0]

        chosen_path = os.path.join(chosen_folder, chosen_file)

        # Try silent mode first
        try:
            proc = subprocess.run([chosen_path, "/S"], capture_output=True, text=True, timeout=300)
            out = (proc.stdout or "") + (proc.stderr or "")
            success = proc.returncode == 0
            if success:
                msg = f"Install attempt for '{chosen_file}': installed successfully\n\nOutput: {out.strip()[:2000]}"
                SESSION["last_action_status"] = msg
                return msg
            else:
                fallback_msg = f"Installer exited with code {proc.returncode}. Output: {out.strip()[:1000]}"
        except Exception as ex_sub:
            fallback_msg = f"Subprocess error: {ex_sub}"
            # If WinError 740, try elevated below

        # Try elevated launch (UAC may appear)
        elevated_ok = _run_elevated(chosen_path, "/S")
        if elevated_ok:
            msg = (
                f"Install launched elevated for '{chosen_file}'. A UAC prompt may have appeared — please accept it to continue.\n"
                "Installer runs separately; check after it finishes. I cannot confirm success from here."
            )
            SESSION["last_action_status"] = msg
            return msg
        else:
            msg = (
                f"⚠️ Could not run installer elevated for '{chosen_file}'.\n"
                f"Reason/fallback: {fallback_msg}\n\n"
                "Try running the Streamlit app as Administrator or run the installer manually (right-click -> Run as administrator)."
            )
            SESSION["last_action_status"] = msg
            return msg

    except Exception as e:
        msg = f"⚠️ Error during install attempt: {e}"
        SESSION["last_action_status"] = msg
        return msg


# -------------------------
# Issue extraction helper
# -------------------------
def extract_issue_from_history(chat_history: List[Tuple[str, str]], current_msg: str) -> str:
    keywords = ["not", "issue", "error", "fail", "disconnect", "slow", "lag", "not working", "problem", "cannot", "unable", "hang", "freeze"]
    for role, msg in reversed(chat_history or []):
        if role == "user":
            low = (msg or "").lower()
            if any(k in low for k in keywords):
                return (msg.split(".")[0]).strip()
    return (current_msg.split(".")[0]).strip()


# -------------------------
# Bedrock fallback helper (format messages safely)
# -------------------------
def call_bedrock_safe(system_prompt: str, chat_history: List[Tuple[str, str]], user_query: str) -> str:
    """
    Format and call Bedrock (Anthropic) safely:
    - system_prompt is passed as top-level "system" field
    - messages are merged so roles alternate (Bedrock requires alternation)
    - every message content is converted to content objects [{"type":"text","text": "..."}]
    """
    if not bedrock_available or bedrock_client is None:
        return "⚠️ Bedrock not configured or unavailable."

    try:
        # Build a flattened history (merge consecutive same-role messages)
        merged = []
        # include chat_history (which is list of tuples)
        for role, text in chat_history or []:
            if not merged or merged[-1][0] != role:
                merged.append([role, text])
            else:
                # append to last
                merged[-1][1] = merged[-1][1] + "\n" + text

        # Ensure last role alternation is safe: final user query appended
        if merged and merged[-1][0] == "user":
            merged[-1][1] = merged[-1][1] + "\n" + user_query
        else:
            merged.append(["user", user_query])

        # Build messages in bedrock format (skip system role; system is top-level)
        formatted_messages = []
        for role, text in merged:
            # only user/assistant allowed
            if role not in ("user", "assistant"):
                # convert unknown role to user
                role = "user"
            formatted_messages.append({
                "role": role,
                "content": [{"type": "text", "text": text}]
            })

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 400,
            "system": system_prompt or "",
            "messages": formatted_messages
        })

        model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
        response = bedrock_client.invoke_model(modelId=model_id, body=body)
        result = json.loads(response["body"].read())
        # result["content"][0]["text"] is typical
        return result.get("content", [{}])[0].get("text", "").strip()
    except Exception as e:
        return f"⚠️ Error communicating with Bedrock: {e}"


# -------------------------
# Human-friendly formatting helpers
# -------------------------
def format_health_summary(summary: dict, suggestion: str) -> str:
    metrics = summary.get("metrics", {})
    updates = summary.get("updates", {})
    critical_logs = summary.get("critical_event_logs", [])
    alerts = summary.get("alerts", [])

    cpu = metrics.get("cpu_usage", "N/A")
    ram = metrics.get("ram_usage", "N/A")
    disk = metrics.get("disk_usage", "N/A")

    update_text = "⚠️ Pending updates available" if updates.get("pending_updates") else "✔️ No pending updates"
    reboot_text = "🔄 System restart required" if updates.get("reboot_required") else "✔️ No restart required"

    if critical_logs:
        log_summary = "\n".join([f"- {l.get('Message', l)}" if isinstance(l, dict) else f"- {l}" for l in critical_logs[:5]])
    else:
        log_summary = "✔ No critical events detected"

    reply = (
        "🩺 System Health Scan Completed\n\n"
        f"🔹 Performance\n"
        f"- CPU Usage: {cpu}%\n"
        f"- RAM Usage: {ram}%\n"
        f"- Disk Usage: {disk}%\n\n"
        f"🔹 Windows Updates\n- {update_text}\n- {reboot_text}\n\n"
        f"🔹 Critical Event Logs\n{log_summary}\n\n"
        f"🤖 Recommendation\n{suggestion}"
    )
    return reply


# -------------------------
# Main entrypoint: get_chatbot_response
# -------------------------
def get_chatbot_response(user_query: str, chat_history: List[Tuple[str, str]]) -> str:
    """
    Main function to call from app.py:
    - user_query: str, latest user message
    - chat_history: list of tuples (role, message) where role is 'user' or 'assistant'
    Returns a string reply (human-friendly).
    """

    uq = (user_query or "").strip()
    low = _normalize(uq)

    # 0) Greeting
    if detect_greeting(uq):
        return (
            "Hello! 👋 I can help with common L1 tasks:\n"
            "- Troubleshoot network (Wi-Fi) and attempt service restart\n"
            "- Restart common services (printer, windows update, dns)\n"
            "- Install applications from the downloads folder (say 'install notepad')\n"
            "- Run a system health scan (say 'run health scan')\n"
            "- Clean temporary files (say 'clear temp')\n\n"
            "If an automated attempt fails, reply 'still not working' and I'll open a ticket for you."
        )

    # 1) Follow-up 'why' questions -> show last action status
    if detect_followup_why(uq):
        last = SESSION.get("last_action_status") or SESSION.get("_last_action_status")
        if last:
            return (
                "Here is what happened with the last automated action:\n\n"
                f"{last}\n\n"
                "Common causes: administrative privileges required, a locked/critical process, or system policy restrictions. "
                "If you want, I can try the action again (may require running the app as Administrator)."
            )
        return "I don't have a record of the last automated action. Which action do you mean?"

    # 2) Escalation: user requests ticket
    if detect_escalation(uq):
        issue = extract_issue_from_history(chat_history, uq)
        ticket = save_ticket(issue)
        return (
            f"🧾 A support ticket has been created for you.\n"
            f"🎫 Ticket ID: {ticket.get('ticket_id')}\n"
            f"📂 Category: {ticket.get('category')}\n"
            f"👨‍💻 Assigned to: {ticket.get('assigned_to')}\n"
            f"👤 Raised by: {ticket.get('username', getpass.getuser())}"
        )

    # 3) Cleanup intent
    if detect_cleanup_intent(uq):
        return perform_cleanup()

    # 4) Restart service
    svc = detect_restart_service_intent(uq)
    if svc:
        return perform_restart_service(svc)

    # 5) Install intent
    app_name = detect_install_intent(uq)
    if app_name:
        return perform_install_app(app_name)

    # 6) Run health scan
    if detect_run_scan(uq):
        if run_health_scan is None:
            return "Health scan module is not available on this system."
        try:
            res = run_health_scan()
            if isinstance(res, tuple):
                summary, suggestion = res
            elif isinstance(res, dict):
                # some versions return {metrics, updates, ...}
                summary = res.get("summary") or res
                suggestion = res.get("suggestion") or res.get("analysis") or "No specific suggestions."
            else:
                return "Health scan returned unexpected result."

            # save last action
            SESSION["last_action_status"] = "Health scan completed."

            return format_health_summary(summary, suggestion)
        except Exception as e:
            SESSION["last_action_status"] = f"Health scan error: {e}"
            return f"⚠️ Error running health scan: {e}"

    # 7) Heuristics for common issues (network, mouse, keyboard, browser)
    if any(k in low for k in ["wifi", "wi-fi", "internet", "disconnect", "network"]):
        # attempt restart and give extended guidance
        svc_name = "WlanSvc"
        restart_msg = perform_restart_service(svc_name)
        extended = (
            "I performed quick Wi-Fi troubleshooting steps. Please try:\n"
            "- Toggle Wi-Fi on your device\n- Restart the router (power cycle) and wait 30s\n- If wired, check the Ethernet cable\n- Try connecting another device to the same network\n- Temporarily disable VPN/Proxy/Firewall to test\n\n"
            "Automated attempt:\n"
        )
        # Append more suggestions to help the user
        more = (
            "\nAdditional suggestions:\n"
            "- Check router admin page for WAN status\n"
            "- On Windows, run: ipconfig /release and ipconfig /renew\n"
            "- Use 'ping 8.8.8.8' to verify connectivity\n"
            "- If using a company network, confirm there are no scheduled network maintenance windows\n"
        )
        return extended + restart_msg + more + "\n\nIf it's still not working, reply 'still not working' and I'll raise a ticket."

    if any(k in low for k in ["mouse", "touchpad", "touch pad", "trackpad"]):
        return (
            "Touchpad troubleshooting steps:\n"
            "1) Ensure the touchpad is enabled in Settings -> Devices -> Touchpad.\n"
            "2) Check Device Manager for driver warnings and update the touchpad driver.\n"
            "3) Try an external USB mouse to continue working meanwhile.\n"
            "4) If touchpad settings include gestures, try resetting them to defaults.\n\n"
            "If this doesn't help, reply 'still not working' to create a ticket."
        )

    if any(k in low for k in ["keyboard", "keys not working", "some keys"]):
        return (
            "Keyboard troubleshooting:\n"
            "1) Reboot the system.\n"
            "2) Try an external USB keyboard to isolate hardware vs software.\n"
            "3) Check Device Manager for keyboard device issues and update drivers.\n\n"
            "If unresolved, say 'still not working' to raise a ticket."
        )

    if any(k in low for k in ["chrome", "edge", "browser", "not opening", "can't open browser", "browser not opening"]):
        return (
            "Browser troubleshooting:\n"
            "- Kill browser processes via Task Manager and reopen.\n"
            "- Try starting browser in safe mode / disable extensions.\n"
            "- Clear browser cache (say 'clear temp').\n"
            "- Check if an antivirus or firewall is blocking the browser.\n\n"
            "If you'd like, I can attempt to clear cache now."
        )

    # 8) Fallback: attempt to use Bedrock/Claude if available for a helpful reply
    if bedrock_available:
        system_prompt = (
            "You are an IT support assistant. Provide step-by-step L1 troubleshooting. "
            "Do NOT escalate unless the user explicitly says 'still not working' or requests a ticket. "
            "Keep responses concise and actionable."
        )
        try:
            ai_reply = call_bedrock_safe(system_prompt, chat_history, user_query)
            # Bedrock may return JSON-like or a long answer — return it directly
            return ai_reply
        except Exception as e:
            # fallback to clarification prompt
            pass

    # 9) Final generic fallback ask for more info
    return (
        "Thanks — I can help with that. Can you briefly describe what you've already tried? "
        "If you'd like me to attempt an automated fix, say 'please try fix' or 'attempt fix'. "
        "If it's still not working after attempts, say 'still not working' and I'll open a ticket."
    )


# -------------------------
# CLI test harness
# -------------------------
if __name__ == "__main__":
    print("Chatbot CLI — type 'exit' to quit")
    hist = []
    while True:
        q = input("You: ").strip()
        if not q:
            continue
        if q.lower() in ("exit", "quit"):
            break
        hist.append(("user", q))
        reply = get_chatbot_response(q, hist)
        hist.append(("assistant", reply))
        print("\nBot:", reply, "\n")
