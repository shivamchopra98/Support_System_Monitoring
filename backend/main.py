# backend/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import time
import json, os

app = FastAPI()

DB_FILE = "agents_db.json"
CMD_FILE = "commands_db.json"

# -------------------------------
# Helpers
# -------------------------------
def load_json(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return {}

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

# -------------------------------
# Models
# -------------------------------
class AgentUpdate(BaseModel):
    agent_id: str
    hostname: str
    username: str
    os: str
    ip_address: str
    metrics: dict
    device_info: dict

class CommandResponse(BaseModel):
    agent_id: str
    command_id: str
    output: str
    success: bool

# -------------------------------
# Register / Update Agent
# -------------------------------
@app.post("/api/agent/update")
def update_agent_info(data: AgentUpdate):
    db = load_json(DB_FILE)
    db[data.agent_id] = {
        "agent_id": data.agent_id,
        "hostname": data.hostname,
        "username": data.username,
        "os": data.os,
        "ip_address": data.ip_address,
        "metrics": data.metrics,
        "device_info": data.device_info,
        "last_seen": time.time()
    }
    save_json(DB_FILE, db)
    return {"status": "ok", "message": "agent info updated"}

# -------------------------------
# Get pending commands for agent
# -------------------------------
@app.get("/api/agent/commands/{agent_id}")
def fetch_commands(agent_id: str):
    cmds = load_json(CMD_FILE)
    if agent_id not in cmds:
        return {"commands": []}
    pending = cmds[agent_id]
    cmds[agent_id] = []  # clear after sending
    save_json(CMD_FILE, cmds)
    return {"commands": pending}

# -------------------------------
# Receive Command Response from Agent
# -------------------------------
@app.post("/api/agent/command_response")
def receive_command_response(resp: CommandResponse):
    print(f"[COMMAND RESPONSE] {resp.agent_id} | CMD: {resp.command_id}")
    print("SUCCESS:", resp.success)
    print("OUTPUT:")
    print(resp.output)
    print("------------------------------------")
    return {"status": "received"}

# -------------------------------
# Admin -> queue command for agent
# -------------------------------
@app.post("/api/agent/send/{agent_id}")
def send_command(agent_id: str, command: Dict[str, Any]):
    cmds = load_json(CMD_FILE)
    if agent_id not in cmds:
        cmds[agent_id] = []
    cmds[agent_id].append(command)
    save_json(CMD_FILE, cmds)
    return {"status": "queued", "command": command}

# -------------------------------
# List agents
# -------------------------------
@app.get("/api/agent/list")
def list_agents():
    db = load_json(DB_FILE)
    devices = []
    for agent_id, info in db.items():
        last_seen = info.get("last_seen", 0)
        online = (time.time() - last_seen) < 30  # online if heartbeat < 30 sec
        devices.append({
            "agent_id": agent_id,
            "hostname": info.get("hostname"),
            "username": info.get("username"),
            "ip_address": info.get("ip_address"),
            "os": info.get("os"),
            "online": online
        })
    return {"devices": devices}

# -------------------------------
# Full agent info
# -------------------------------
@app.get("/api/agent/info/{agent_id}")
def full_agent_info(agent_id: str):
    db = load_json(DB_FILE)
    if agent_id not in db:
        raise HTTPException(status_code=404, detail="Agent not found")
    return db[agent_id]
