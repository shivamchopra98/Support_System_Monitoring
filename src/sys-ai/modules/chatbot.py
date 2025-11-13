# chatbot.py
"""
Comprehensive chatbot module for SYS-AI.

Features:
- Intent detection (cleanup, restart service, install app, run health scan, follow-up)
- Safe action executors (restart service, cleanup, install)
- Ticket creation via save_ticket when escalation requested
- Bedrock AI fallback (messages formatted properly)
- Streamlit session_state integration for last action tracking
- CLI interactive mode for testing
"""

import os
import re
import json
import time
import ctypes
import shutil
import subprocess
import subprocess
import os
import ctypes
from typing import List, Tuple, Optional

# Try imports (module may be in modules/ or project root)
try:
    from modules.ticket_classifier import save_ticket, classify_ticket
except Exception:
    try:
        from ticket_classifier import save_ticket, classify_ticket  # type: ignore
    except Exception:
        # fallback stub for testing (won't persist)
        def save_ticket(issue):
            return {"ticket_id": "INC0000000", "category": "General Support", "assigned_to": "L1"}

        def classify_ticket(issue):
            return "General Support"

# Try health-scan import (proactive module)
try:
    from modules.proactive_health import system_health_prediction as run_health_scan
except Exception:
    try:
        from modules.system_health_agent import run_health_scan  # type: ignore
    except Exception:
        run_health_scan = None  # may be None if not present

# Try Bedrock client when needed
bedrock_available = False
try:
    import boto3  # only used if Bedrock fallback is desired
    bedrock_client = boto3.client(service_name="bedrock-runtime", region_name="us-east-1")
    bedrock_available = True
except Exception:
    bedrock_client = None
    bedrock_available = False

# Streamlit session state
try:
    import streamlit as st  # type: ignore
    SESSION = st.session_state
except Exception:
    # CLI / test fallback
    SESSION = globals().setdefault("_chatbot_session_state", {})


# ---------------------------
# Utility / Intent Detection
# ---------------------------
def _normalize(text: str) -> str:
    return (text or "").strip().lower()


def detect_greeting(text: str) -> bool:
    t = _normalize(text)
    greetings = [
        "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
        "greetings", "yo", "sup", "what's up", "whats up"
    ]
    return any(t == g or t.startswith(g) for g in greetings)


def detect_cleanup_intent(text: str) -> bool:
    text = _normalize(text)
    return any(k in text for k in ["clear temp", "clear cache", "cleanup", "clean temp", "delete temp", "remove temp"])


def detect_restart_service_intent(text: str) -> Optional[str]:
    """
    Return a Windows service name to restart, or "generic"/None.
    """
    text = _normalize(text)
    mapping_phrases = {
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
    for k, svc in mapping_phrases.items():
        if k in text:
            return svc
    if "restart service" in text or "restart the service" in text:
        return "generic"
    return None


def detect_install_intent(text: str) -> Optional[str]:
    t = _normalize(text)
    if t.startswith("install ") or " install " in t:
        # heuristic: capture phrase after 'install'
        m = re.search(r"install\s+([a-z0-9\-\_\. ]+)", t)
        if m:
            return m.group(1).strip()
        return "unknown"
    return None


def detect_run_scan(text: str) -> bool:
    t = _normalize(text)
    return any(k in t for k in ["run health scan", "run scan", "system scan", "health scan", "diagnostic", "run scan"])


def detect_escalation(text: str) -> bool:
    t = _normalize(text)
    return any(p in t for p in ["still not working", "raise a ticket", "create ticket", "open a ticket", "not resolved", "escalate"])


def detect_followup_why(text: str) -> bool:
    t = _normalize(text)
    return any(w in t for w in ["why", "what happened", "explain", "reason", "why did", "why it failed"])


# ---------------------------
# Cleanup functions
# ---------------------------
def _clean_path(path: Optional[str]) -> Tuple[int, int]:
    removed_files = 0
    removed_bytes = 0
    if not path:
        return removed_files, removed_bytes
    try:
        if not os.path.exists(path):
            return removed_files, removed_bytes
        # Only delete files inside, not the root folder itself
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
                # try to rmdir empty dir
                try:
                    os.rmdir(os.path.join(root, d))
                except Exception:
                    pass
    except Exception:
        pass
    return removed_files, removed_bytes


def empty_recycle_bin() -> bool:
    try:
        # 0x00000007 = no confirmation, no progress UI, no sound
        ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x00000007)
        return True
    except Exception:
        return False


def perform_cleanup() -> str:
    """
    Clean only:
      - Windows Temp
      - User Temp
      - CrashDumps
      - Chrome Cache
      - Edge Cache
      - Recycle Bin
    """
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
    mb = total_bytes / (1024 * 1024) if total_bytes else 0
    return (
        f"🧹 Cleanup finished: removed {total_files} files (~{mb:.2f} MB).\n"
        f"Locations cleaned: Windows Temp, User Temp, CrashDumps, Chrome & Edge caches.\n"
        f"Recycle Bin: {'Emptied' if recycle_ok else 'Failed/Permission denied'}."
    )


# ---------------------------
# Restart service
# ---------------------------
def perform_restart_service(service_name: str) -> str:
    if service_name == "generic":
        return "Please specify which service to restart (e.g., 'restart Wi-Fi' or 'restart printer service')."
    try:
        stop_cmd = ["sc", "stop", service_name]
        start_cmd = ["sc", "start", service_name]
        stop_proc = subprocess.run(stop_cmd, capture_output=True, text=True, timeout=30)
        stop_out = (stop_proc.stdout or "") + (stop_proc.stderr or "")
        # small pause
        time.sleep(1)
        start_proc = subprocess.run(start_cmd, capture_output=True, text=True, timeout=30)
        start_out = (start_proc.stdout or "") + (start_proc.stderr or "")
        status_msg = f"Restart attempt for service '{service_name}':\n\nSTOP output:\n{stop_out.strip()}\n\nSTART output:\n{start_out.strip()}"
        if "Access is denied" in stop_out or "Access is denied" in start_out:
            status_msg = f"⚠️ Error restarting {service_name}: Access is denied. Try running the app as Administrator."
        # Save last action
        try:
            SESSION["last_action_status"] = status_msg
        except Exception:
            SESSION["_last_action_status"] = status_msg
        return status_msg
    except subprocess.TimeoutExpired:
        msg = f"⚠️ Timeout while attempting to restart {service_name}."
        SESSION["last_action_status"] = msg
        return msg
    except Exception as e:
        msg = f"⚠️ Error restarting {service_name}: {e}"
        SESSION["last_action_status"] = msg
        return msg
    
    # ---------- helper to run elevated via ShellExecuteW ----------
def _run_elevated(exe_path, args=""):
    """
    Launch exe_path elevated using ShellExecuteW.
    Returns True if ShellExecuteW successfully started the process (note: does not guarantee install success),
    False otherwise.
    """
    try:
        # ShellExecuteW returns a value > 32 on success
        params = args or ""
        rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe_path, params, None, 1)
        return rc > 32
    except Exception:
        return False


# ---------------------------
# Install application
# ---------------------------
WINDOWS_DOWNLOADS = os.path.join(os.path.expanduser("~"), "downloads")
PROJECT_DOWNLOADS = os.path.join(os.path.dirname(__file__), "downloads")

SEARCH_LOCATIONS = [
    PROJECT_DOWNLOADS,      # 1st priority
    WINDOWS_DOWNLOADS       # fallback
]


def perform_install_app(app_name: str) -> str:
    try:
        exe_files = []

        # Search both download locations (project first)
        for folder in SEARCH_LOCATIONS:
            if folder and os.path.exists(folder):
                for f in os.listdir(folder):
                    if f.lower().endswith(".exe"):
                        exe_files.append((folder, f))

        if not exe_files:
            return "No .exe installers found in either the project downloads or your user Downloads folder."

        app_norm = (app_name or "").lower()
        chosen_path = None
        chosen_name = None

        if app_norm and app_norm != "unknown":
            for folder, fname in exe_files:
                if app_norm in fname.lower():
                    chosen_path = os.path.join(folder, fname)
                    chosen_name = fname
                    break

        if not chosen_path:
            folder, fname = exe_files[0]
            chosen_path = os.path.join(folder, fname)
            chosen_name = fname

        # First try silent install via subprocess
        try:
            proc = subprocess.run([chosen_path, "/S"], capture_output=True, text=True, timeout=300)
            out = (proc.stdout or "") + (proc.stderr or "")
            success = proc.returncode == 0
            if success:
                msg = f"Install attempt for '{chosen_name}': installed successfully\n\nOutput: {out.strip()[:2000]}"
                SESSION["last_action_status"] = msg
                return msg
            else:
                # If returncode non-zero, include output and continue to attempt elevated launch
                fallback_msg = f"Installer finished with exit code {proc.returncode}. Output: {out.strip()[:1000]}"
        except Exception as ex_sub:
            # capture exception: often WinError 740 ends up here
            fallback_msg = f"Subprocess error: {ex_sub}"

            # Special-case: if WinError 740 (requires elevation), try ShellExecute
            if isinstance(ex_sub, OSError) and getattr(ex_sub, "winerror", None) == 740:
                # we'll attempt ShellExecuteW below
                pass

        # If we reach here, try elevated launch (this will trigger a UAC prompt)
        elevated_ok = _run_elevated(chosen_path, "/S")
        if elevated_ok:
            msg = (
                f"Install launched elevated for '{chosen_name}'. A UAC prompt may have appeared — "
                "please accept it to continue the install. The installer runs in a separate process.\n\n"
                f"Note: I cannot confirm success until the installer finishes; check the program after install."
            )
            SESSION["last_action_status"] = msg
            return msg
        else:
            # Could not start elevated; inform user and suggest running Streamlit as admin
            msg = (
                f"⚠️ Could not run installer elevated for '{chosen_name}'.\n"
                f"Reason: {fallback_msg}\n\n"
                "Try one of the following:\n"
                "• Run the Streamlit app/terminal as Administrator and try again.\n"
                "• Manually right-click the installer and choose 'Run as administrator'.\n"
                "• If the installer does not support silent mode, try running it manually to proceed.\n"
            )
            SESSION["last_action_status"] = msg
            return msg

    except Exception as e:
        SESSION["last_action_status"] = f"Install error: {e}"
        return f"⚠️ Error during install attempt: {e}"


# ---------------------------
# Helper: extract issue text
# ---------------------------
def extract_issue_from_history(chat_history: List[Tuple[str, str]], current_msg: str) -> str:
    keywords = ["not", "issue", "error", "fail", "disconnect", "slow", "lag", "not working", "problem", "cannot", "unable"]
    for role, msg in reversed(chat_history or []):
        if role == "user":
            low = (msg or "").lower()
            if any(k in low for k in keywords):
                return (msg.split(".")[0]).strip()
    return (current_msg.split(".")[0]).strip()


# ---------------------------
# Bedrock fallback (if enabled)
# ---------------------------
def call_bedrock(messages: List[dict]) -> str:
    if not bedrock_available or bedrock_client is None:
        return "⚠️ Bedrock not configured or unavailable."

    try:
        model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
        # system content extraction
        system_content = ""
        if messages and messages[0].get("role") == "system":
            system_content = messages[0].get("content", "")

        formatted = []
        for m in messages:
            # skip top-level system in messages list when sending to bedrock API body
            if m.get("role") == "system":
                continue
            # bedrock expects content objects for each message
            formatted.append({
                "role": m.get("role"),
                "content": [{"type": "text", "text": m.get("content", "")}]
            })

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 400,
            "system": [system_content] if system_content else [],
            "messages": formatted
        })
        response = bedrock_client.invoke_model(modelId=model_id, body=body)
        result = json.loads(response["body"].read())
        # result structure: result["content"][0]["text"]
        return result.get("content", [{}])[0].get("text", "").strip()
    except Exception as e:
        return f"⚠️ Error communicating with Bedrock: {e}"


# ---------------------------
# Main entry
# ---------------------------
def get_chatbot_response(user_query: str, chat_history: List[Tuple[str, str]]) -> str:
    uq = (user_query or "").strip()
    low = _normalize(uq)

    # 0) Greeting
    if detect_greeting(uq):
        return (
            "Hello! 👋 How can I assist you today?\n\n"
            "You can ask me to:\n"
            "- Fix Wi-Fi / network problems\n"
            "- Install applications \n"
            "- Restart services (printer, wifi, windows update)\n"
            "- Clean temporary files and caches\n"
            "- Run a system health scan\n"
            "If an automated fix fails, reply 'still not working' and I'll raise a ticket."
        )

    # 1) Follow-up "why" about last automated action
    if detect_followup_why(uq):
        last = SESSION.get("last_action_status") or SESSION.get("_last_action_status")
        if last:
            return (
                "Here is what happened with the last automated action:\n\n"
                f"{last}\n\n"
                "Common causes: admin privileges required, a locked process, or system policy restrictions. "
                "I can attempt again if you allow (may require Administrator)."
            )
        return "I don't have a record of the last automated action. Which action do you mean?"

    # 2) Escalation -> create ticket
    if detect_escalation(uq):
        issue = extract_issue_from_history(chat_history, uq)
        ticket = save_ticket(issue)
        return (
            f"🧾 A support ticket has been created for you.\n"
            f"🎫 Ticket ID: {ticket.get('ticket_id')}\n"
            f"📂 Category: {ticket.get('category')}\n"
            f"👨‍💻 Assigned to: {ticket.get('assigned_to')}"
        )

    # 3) Cleanup intent
    if detect_cleanup_intent(uq):
        return perform_cleanup()

    # 4) Restart service
    svc = detect_restart_service_intent(uq)
    if svc:
        return perform_restart_service(svc)

    # 5) Install app
    app_name = detect_install_intent(uq)
    if app_name:
        return perform_install_app(app_name)

    # 6) Run health scan
    if detect_run_scan(uq):
        if run_health_scan is None:
            return "Health scan module is not available on this system."

    try:
        res = run_health_scan()

        # Normalize formats
        if isinstance(res, tuple):
            summary, suggestion = res
        elif isinstance(res, dict):
            summary = res.get("summary") or res
            suggestion = res.get("suggestion") or res.get("analysis") or "No additional suggestions available."
        else:
            return "Health scan returned unexpected data."

        metrics = summary.get("metrics", {})
        updates = summary.get("updates", {})
        critical_logs = summary.get("critical_event_logs", [])
        alerts = summary.get("alerts", [])

        # -------------------------
        # Human-readable formatting
        # -------------------------
        cpu = metrics.get("cpu_usage", "N/A")
        ram = metrics.get("ram_usage", "N/A")
        disk = metrics.get("disk_usage", "N/A")

        update_text = (
            "⚠️ Pending updates available" if updates.get("pending_updates") 
            else "✔️ No pending updates"
        )
        reboot_text = (
            "🔄 System restart required" if updates.get("reboot_required")
            else "✔️ No restart required"
        )

        # Critical logs summary
        if critical_logs:
            log_summary = "\n".join([f"- {log.get('Message','')}" for log in critical_logs[:5]])
        else:
            log_summary = "✔ No critical events detected"

        # Build final readable message
        formatted_reply = f"""
🩺 **System Health Scan Completed**

### 🔹 Performance
- **CPU Usage:** {cpu}%
- **RAM Usage:** {ram}%
- **Disk Usage:** {disk}%

### 🔹 Windows Updates
- {update_text}
- {reboot_text}

### 🔹 Critical Event Logs
{log_summary}

### 🤖 Recommendation
{suggestion}
"""

        # Save last action
        SESSION["last_action_status"] = "Health scan completed."

        return formatted_reply.strip()

    except Exception as e:
        SESSION["last_action_status"] = f"Health scan error: {e}"
        return f"⚠️ Error running health scan: {e}"

    # 7) Heuristics for common issues (network, browser, input)
    if any(k in low for k in ["wifi", "wi-fi", "internet", "disconnect", "network"]):
        restart_msg = perform_restart_service("WlanSvc")
        base = (
            "I performed quick Wi-Fi troubleshooting steps. Try:\n"
            "- Toggle Wi-Fi on your device\n- Restart your router\n- Check cable if wired\n- Try another device on same network\n\n"
            "Automated attempt result:\n"
        )
        return base + restart_msg + "\n\nIf it's still not working, reply 'still not working' and I'll raise a ticket."

    if any(k in low for k in ["mouse", "touchpad", "touch pad", "trackpad"]):
        return (
            "Touchpad troubleshooting:\n"
            "1) Check Settings -> Devices -> Touchpad and ensure enabled.\n"
            "2) Update touchpad driver in Device Manager.\n"
            "3) Connect external mouse to continue.\n"
            "If you'd like, say 'still not working' to create a ticket."
        )

    if any(k in low for k in ["keyboard", "keys not working", "some keys"]):
        return (
            "Keyboard troubleshooting:\n"
            "1) Reboot system.\n"
            "2) Try external USB keyboard.\n"
            "3) Check Device Manager for issues.\n"
            "If unresolved reply 'still not working' to create a ticket."
        )

    if any(k in low for k in ["chrome", "edge", "browser", "not opening", "can't open browser", "browser not opening"]):
        return (
            "Browser troubleshooting suggestions:\n"
            "- Kill browser processes and reopen.\n- Try safe mode / disable extensions.\n- Clear cache (say 'clear temp').\nIf you'd like, I can attempt to clear caches now."
        )

    # 8) Final fallback: call Bedrock (if available) or ask clarifying question
    # if bedrock_available:
    #     # Build messages using the pattern: system + history + user
    #     messages = []
    #     messages.append({"role": "system", "content": "You are an IT support assistant. Provide actionable, step-by-step L1 help. Only escalate/create ticket when user explicitly asks 'still not working'."})
    #     for role, msg in chat_history:
    #         if role in ("user", "assistant"):
    #             messages.append({"role": role, "content": msg})
    #     messages.append({"role": "user", "content": user_query})
    #     ai_reply = call_bedrock(messages)
    #     return ai_reply

    # # No Bedrock: ask clarifying question instead of aggressive action
    # return (
    #     "Thanks — I can help with that. Can you briefly describe what you've already tried? "
    #     "If you'd like me to attempt an automated fix, say 'please try fix' or 'attempt fix'. "
    #     "If it still doesn't work, say 'still not working' and I'll open a ticket."
    # )


# ---------------------------
# CLI test harness
# ---------------------------
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
        print("Bot:", reply)
