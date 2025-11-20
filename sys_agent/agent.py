# sys_agent/agent.py
import requests
import platform
import psutil
import socket
import time
import subprocess
import json
import os
import uuid
import webbrowser

def launch_quick_assist():
    """
    Launch Quick Assist (Store version + Win32 version support)
    """

    # 1) Try launching Microsoft Store Quick Assist via AppModelID
    try:
        app_id = "MicrosoftCorporationII.QuickAssist_8wekyb3d8bbwe!App"
        subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{app_id}"])
        return True, "Launched Quick Assist (Store App via AppID)"
    except Exception as e:
        pass

    # 2) Try URI protocol
    try:
        subprocess.Popen(["explorer.exe", "ms-quickassist:"])
        return True, "Launched Quick Assist via URI"
    except:
        pass

    # 3) Try System32 version
    sys32_exe = r"C:\Windows\System32\quickassist.exe"
    if os.path.exists(sys32_exe):
        try:
            subprocess.Popen([sys32_exe])
            return True, "Launched Quick Assist (System32)"
        except:
            pass

    # 4) Try WindowsApps folder
    import glob
    base = r"C:\Program Files\WindowsApps"
    try:
        for folder in glob.glob(os.path.join(base, "MicrosoftCorporationII.QuickAssist_*")):
            exe = os.path.join(folder, "QuickAssist.exe")
            if os.path.exists(exe):
                subprocess.Popen(["explorer.exe", exe])
                return True, f"Launched Quick Assist (Store EXE via explorer)"
    except:
        pass

    return False, "Failed to launch Quick Assist"

# configure your backend url here
BACKEND_URL = "http://172.16.1.41:8000"   # change as needed

# ---------------------------------------------------
# Unique persistent agent id per machine
# ---------------------------------------------------
def get_agent_id():
    agent_file = "agent_id.txt"
    if not os.path.exists(agent_file):
        hostname = platform.node()
        unique = str(uuid.uuid4()).split("-")[0]
        agent_id = f"INL-{hostname}-{unique}"
        with open(agent_file, "w") as f:
            f.write(agent_id)
        return agent_id
    return open(agent_file, "r").read().strip()

AGENT_ID = get_agent_id()

# ---------------------------------------------------
# Real LAN IP detection (works in most networks)
# ---------------------------------------------------
def get_real_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "0.0.0.0"

# ---------------------------------------------------
# metrics and device info
# ---------------------------------------------------
def collect_metrics():
    return {
        "cpu_usage": psutil.cpu_percent(interval=1),
        "ram_usage": psutil.virtual_memory().percent,
        "disk_usage": psutil.disk_usage(os.path.abspath(os.sep)).percent
    }

def collect_device_info():
    try:
        proc = platform.processor()
    except:
        proc = "Unknown"
    return {
        "hostname": platform.node(),
        "manufacturer": platform.machine(),
        "processor": proc,
        "platform": platform.platform(),
        "boot_time": psutil.boot_time()
    }

# ---------------------------------------------------
# send update
# ---------------------------------------------------
def send_update():
    try:
        ip = get_real_ip()  # or existing ip detection
    except Exception:
        ip = "0.0.0.0"

    payload = {
        "agent_id": AGENT_ID,
        "hostname": platform.node(),
        "username": os.environ.get("USERNAME", "unknown"),
        "os": platform.platform(),
        "ip_address": ip,
        "metrics": collect_metrics(),
        "device_info": collect_device_info()
    }

    try:
        r = requests.post(f"{BACKEND_URL}/api/agent/update", json=payload, timeout=5)
        if r.status_code == 200:
            print("[INFO] Agent info updated")
            return True
        else:
            print(f"[WARN] Registration returned {r.status_code} / {r.text}")
            return False
    except Exception as e:
        print("[ERROR] Update failed:", e)
        return False

# ---------------------------------------------------
# run commands (from admin)
# ---------------------------------------------------
def run_command(cmd):
    try:
        ctype = cmd.get("type")
        if ctype == "shutdown":
            subprocess.run(["shutdown", "/s", "/t", "5"], shell=True)
            return True, "Shutdown triggered"
        if ctype == "restart":
            subprocess.run(["shutdown", "/r", "/t", "5"], shell=True)
            return True, "Restart triggered"
        if ctype == "quick_assist":
            success, msg = launch_quick_assist()
            return success, msg
        if ctype == "cmd":
            result = subprocess.getoutput(cmd.get("command", ""))
            return True, result
        return False, "Unknown command type"
    except Exception as e:
        return False, str(e)

# ---------------------------------------------------
# send command response to backend
# ---------------------------------------------------
def send_command_response(cmd_id, success, output):
    payload = {
        "agent_id": AGENT_ID,
        "command_id": cmd_id,
        "output": output,
        "success": success
    }
    try:
        requests.post(f"{BACKEND_URL}/api/agent/command_response", json=payload, timeout=5)
    except Exception as e:
        print("[ERROR] send_command_response failed:", e)

# ---------------------------------------------------
# poll backend for commands
# ---------------------------------------------------
def poll_commands():
    try:
        r = requests.get(f"{BACKEND_URL}/api/agent/commands/{AGENT_ID}", timeout=5)
        commands = r.json().get("commands", [])
        for cmd in commands:
            print(f"[COMMAND] Received: {cmd}")
            success, output = run_command(cmd)
            send_command_response(cmd.get("id", ""), success, output)
    except Exception as e:
        print("[ERROR] Poll failed:", e)

# ---------------------------------------------------
# main
# ---------------------------------------------------
if __name__ == "__main__":
    print(f"[INFO] Starting SysAI Agent (agent_id={AGENT_ID})")
    browser_opened_flag = os.path.join(os.path.dirname(__file__), ".opened_browser")

    try:
        while True:
            updated = send_update()
            # If registration/update succeeded and browser not opened yet, open demo URL
            try:
                if updated and not os.path.exists(browser_opened_flag):
                    # Build URL to Streamlit app on admin machine (adjust port if needed)
                    streamlit_url = f"http://172.16.1.41:8501/?agent_id={AGENT_ID}"
                    print(f"[INFO] Opening streamlit URL in default browser: {streamlit_url}")
                    try:
                        webbrowser.open(streamlit_url, new=2)  # open new tab if possible
                        # create flag file to avoid repeated opens
                        open(browser_opened_flag, "w").write(str(time.time()))
                    except Exception as e:
                        print("[WARN] Could not open browser automatically:", e)
            except Exception:
                pass

            poll_commands()
            time.sleep(5)
    except KeyboardInterrupt:
        print("[INFO] Agent stopped by user")
