import threading
import time
import uuid
import platform
import socket
import psutil
import requests
import os
import subprocess
import json
from datetime import datetime

# Configure - EDIT to point to your backend
BACKEND_BASE = os.environ.get("SYS_AI_BACKEND", "http://YOUR_BACKEND_HOST:8000")
API_TOKEN = os.environ.get("SYS_AI_AGENT_TOKEN", "replace-with-strong-token")

HEADERS = {"Authorization": f"Bearer {API_TOKEN}", "Content-Type": "application/json"}

def get_system_info():
    try:
        hostname = socket.gethostname()
        uname = platform.uname()
        ram = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=1)
        disk = {p.device: psutil.disk_usage(p.mountpoint)._asdict() for p in psutil.disk_partitions() if os.path.exists(p.mountpoint)}
        info = {
            "agent_id": AGENT_ID,
            "hostname": hostname,
            "username": os.getlogin(),
            "platform": platform.platform(),
            "cpu_percent": cpu_percent,
            "ram_total_gb": round(ram.total / (1024**3), 2),
            "ram_used_gb": round(ram.used / (1024**3), 2),
            "disk": {k: {"total_gb": round(v.total/(1024**3),2), "free_gb": round(v.free/(1024**3),2)} for k,v in disk.items()},
            "timestamp": datetime.utcnow().isoformat()
        }
        return info
    except Exception as e:
        return {"error": str(e), "agent_id": AGENT_ID, "timestamp": datetime.utcnow().isoformat()}

# Unique agent id (persist to file)
AGENT_ID_FILE = os.path.join(os.path.expanduser("~"), ".sysai_agent_id")

def load_or_create_agent_id():
    if os.path.exists(AGENT_ID_FILE):
        try:
            return open(AGENT_ID_FILE).read().strip()
        except:
            pass
    new_id = str(uuid.uuid4())
    try:
        open(AGENT_ID_FILE, "w").write(new_id)
    except:
        pass
    return new_id

AGENT_ID = load_or_create_agent_id()

class AgentWorker:
    def __init__(self, interval=30):
        self.interval = interval
        self._running = False
        self.thread = None

    def run_loop(self):
        self._running = True
        while self._running:
            try:
                # 1) collect metrics and send
                info = get_system_info()
                url = f"{BACKEND_BASE}/api/agent/update"
                resp = requests.post(url, headers=HEADERS, json=info, timeout=15)
                # ignore resp unless auth fails
            except Exception as e:
                # optionally log to file
                pass

            try:
                # 2) poll for commands
                cmd_url = f"{BACKEND_BASE}/api/agent/commands/{AGENT_ID}"
                r = requests.get(cmd_url, headers=HEADERS, timeout=15)
                if r.status_code == 200:
                    commands = r.json().get("commands", [])
                    for cmd in commands:
                        self.execute_command(cmd)
            except Exception as e:
                pass

            # wait
            for _ in range(int(self.interval)):
                if not self._running:
                    break
                time.sleep(1)

    def run(self):
        self.thread = threading.Thread(target=self.run_loop, daemon=True)
        self.thread.start()
        # keep the main thread alive
        while self._running or self.thread.is_alive():
            time.sleep(1)

    def stop(self):
        self._running = False
        if self.thread:
            self.thread.join(timeout=5)

    def execute_command(self, cmd):
        """
        cmd: dict with fields: id, type, payload
        supported types: restart_service, run_shell, open_quick_assist
        """
        try:
            cmd_id = cmd.get("id")
            ctype = cmd.get("type")
            payload = cmd.get("payload", {})
            result = {"cmd_id": cmd_id, "agent_id": AGENT_ID, "status": "unknown", "output": "", "timestamp": datetime.utcnow().isoformat()}

            if ctype == "restart_service":
                service_name = payload.get("service")
                # Use sc to stop/start
                stop = subprocess.run(["sc", "stop", service_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
                start = subprocess.run(["sc", "start", service_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
                result["status"] = "ok"
                result["output"] = f"stop: {stop.stdout}\nstart: {start.stdout}"
            elif ctype == "run_shell":
                shell = payload.get("cmd")
                r = subprocess.run(shell, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
                result["status"] = "ok" if r.returncode==0 else "error"
                result["output"] = r.stdout + r.stderr
            elif ctype == "open_quick_assist":
                # launch Quick Assist via Shell method
                try:
                    os.system(r'start "" "shell:appsFolder\MicrosoftCorporationII.QuickAssist_8wekyb3d8bbwe!App"')
                    result["status"] = "ok"
                    result["output"] = "Quick Assist launched"
                except Exception as e:
                    result["status"] = "error"
                    result["output"] = str(e)
            else:
                result["status"] = "error"
                result["output"] = f"Unknown command type: {ctype}"

            # Post result back
            try:
                post_url = f"{BACKEND_BASE}/api/agent/command_response"
                requests.post(post_url, headers=HEADERS, json=result, timeout=15)
            except:
                pass

        except Exception as e:
            # on exception post failure
            try:
                post_url = f"{BACKEND_BASE}/api/agent/command_response"
                requests.post(post_url, headers=HEADERS, json={"agent_id": AGENT_ID, "status": "error", "output": str(e)}, timeout=10)
            except:
                pass
