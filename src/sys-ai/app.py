# src/sys-ai/app.py  (FULL updated file)
import json
import streamlit as st
import requests
import socket
import pandas as pd
import psutil
import shutil
import time
import os
import subprocess
import uuid
import getpass

from st_aggrid import AgGrid, GridOptionsBuilder
from modules.ticket_classifier import classify_ticket, save_ticket
from modules.chatbot import get_chatbot_response
from modules.auto_troubleshoot import restart_service
from modules.application_installer import application_installer_ui, admin_approval_ui
from modules.proactive_health import system_health_prediction
from modules.chat_support import add_message, get_chat_for_user, get_active_users, load_chat

# Add admin machine agent IDs here
ADMIN_AGENT_IDS = [
    "INL-ADMINPC-abc123"   # replace with your admin PC agent_id
]

# Current OS username (used to detect Admin Portal access)
current_user = getpass.getuser()

# -------------------------
# CONFIG
# -------------------------
st.set_page_config(page_title="SYS AI - L1 Support", layout="wide")
BACKEND_URL = st.session_state.get("backend_url", "http://172.16.1.41:8000")  # change as needed

# -------------------------
# Helpers
# -------------------------

def launch_quick_assist():
    try:
        # Windows Quick Assist path
        qa_path = r"C:\Windows\System32\quickassist.exe"

        if os.path.exists(qa_path):
            subprocess.Popen([qa_path])
        else:
            # Sometimes Windows stores it inside WinSxS
            subprocess.Popen(["quickassist.exe"])

        return True
    except Exception as e:
        st.error(f"Unable to launch Quick Assist: {e}")
        return False
    
def trigger_quick_assist(agent_id: str):
    try:
        payload = {"id": f"qa-{int(time.time())}", "type": "quick_assist"}
        r = requests.post(f"{BACKEND_URL}/api/agent/send/{agent_id}", json=payload, timeout=5)
        return r.status_code == 200
    except:
        return False

def get_client_ip():
    """Try several methods to obtain the real client IP when using Streamlit."""
    try:
        # Common (if deployed behind reverse proxy)
        return st.context.headers.get("X-Forwarded-For") or st.context.request.remote_addr
    except Exception:
        # fallback - best-effort
        try:
            from streamlit.runtime.scriptrunner import get_script_run_ctx
            from streamlit.web.server.server import Server
            ctx = get_script_run_ctx()
            if ctx:
                session_info = Server.get_current()._session_info_by_id.get(ctx.session_id)
                if session_info:
                    return session_info.ws.request.remote_ip
        except Exception:
            pass
    return None

def fetch_agents():
    try:
        r = requests.get(f"{BACKEND_URL}/api/agent/list", timeout=5)
        return r.json().get("devices", [])
    except Exception:
        return []

def detect_agent_by_identity(param_agent=None, client_ip=None, local_hostname=None, agents=None):
    """
    Return detected agent dict (or None).
    Priority: URL param -> hostname match -> IP match -> session_state fallback
    """
    agents = agents if agents is not None else fetch_agents()

    # 1) URL param takes precedence
    if param_agent:
        for a in agents:
            if a.get("agent_id") == param_agent or a.get("hostname") == param_agent:
                return a

    # 2) Hostname match (case-insensitive)
    if local_hostname:
        for a in agents:
            if a.get("hostname", "").lower() == str(local_hostname).lower():
                return a

    # 3) IP match
    if client_ip:
        for a in agents:
            if a.get("ip_address") == client_ip:
                return a

    # 4) session fallback
    if "current_user_agent" in st.session_state:
        aid = st.session_state["current_user_agent"]
        for a in agents:
            if a.get("agent_id") == aid:
                return a

    return None

def get_agent_info(agent_id):
    """Fetch full agent info from backend or return None."""
    try:
        r = requests.get(f"{BACKEND_URL}/api/agent/info/{agent_id}", timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

# -------------------------
# CSS / UI setup
# -------------------------
def set_custom_css():
    st.markdown(
        """
       <style>
       /* Hide floating buttons globally */
#chat-float-btn, #admin-float-btn {
    display: none !important;
}

/* Floating button base style */
.floating-btn {
    position: fixed;
    bottom: 28px;
    right: 28px;
    background: #1a69bb;
    color: white;
    padding: 14px 18px;
    border-radius: 50px;
    font-size: 18px;
    border: none;
    cursor: pointer;
    z-index: 9999;
    box-shadow: 0px 4px 12px rgba(0,0,0,0.3);
}
.floating-btn:hover {
    background: #144f8a;
}
        body {
            background-color: #fff;
            color: #2b3b99;
        }
        .stApp {
            background-color: #fff;
        }
        [data-testid="stSidebar"] {
            background-image: linear-gradient(45deg, #2d3695,#1a69bb);
            padding: 20px;
        }
        [data-testid="stSidebar"] * {
            color: #fff !important;
        }
        .usage-card {
            background: #E3E3E3;
            border-radius: 20px;
            padding: 20px;
            text-align: center;
            box-shadow: 8px 8px 16px #b8b8b8, -8px -8px 16px #ffffff;
        }
        .gauge-container {
            width: 140px;
            height: 140px;
            border-radius: 50%;
            background: linear-gradient(145deg, #cacaca, #ffffff);
            box-shadow: 8px 8px 16px #b8b8b8, -8px -8px 16px #ffffff;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 22px;
            font-weight: bold;
            color: black;
            position: relative;
        }
        .gauge-container::before {
            content: "";
            position: absolute;
            width: 130px;
            height: 130px;
            border-radius: 50%;
            background: #E3E3E3;
            box-shadow: inset 4px 4px 8px #b8b8b8, inset -4px -4px 8px #ffffff;
        }
        .gauge-text {
            position: absolute;
            z-index: 10;
            font-size: 24px;
            font-weight: bold;
        }
        .ram { background: #4CAF50; }
        .cpu { background: #FFC107; }
        .disk { background: #F44336; }
        .status-good { background-color: #D4EDDA; border-left: 5px solid green; padding: 15px; border-radius: 10px; }
        .status-warning { background-color: #FFF3CD; border-left: 5px solid orange; padding: 15px; border-radius: 10px; }
        .status-critical { background-color: #F8D7DA; border-left: 5px solid red; padding: 15px; border-radius: 10px; }
       </style>
        """,
        unsafe_allow_html=True,
    )

set_custom_css()

# -------------------------
# Determine viewer identity EARLY so we can show/hide Admin in sidebar
# -------------------------
# Default admin users (these are usernames reported by agents)
ADMIN_USERS = ["ShivamChopra", "Administrator", "admin"]

# attempt detection now (best-effort). This must be done prior to building the sidebar menu.
client_ip_guess = get_client_ip()
hostname_guess = None
try:
    hostname_guess = socket.gethostname()
except Exception:
    hostname_guess = None

# param agent from URL (if user opened with ?agent_id=)
url_param_agent = None
if st.query_params and "agent_id" in st.query_params:
    p = st.query_params.get("agent_id")
    if isinstance(p, list):
        url_param_agent = p[0]
    else:
        url_param_agent = p

agents_list_for_sidebar = fetch_agents()
viewer_agent = detect_agent_by_identity(param_agent=url_param_agent, client_ip=client_ip_guess, local_hostname=hostname_guess, agents=agents_list_for_sidebar)
viewer_username = None
viewer_agent_id = None
if viewer_agent:
    viewer_agent_id = viewer_agent.get("agent_id")
    info_tmp = get_agent_info(viewer_agent_id)
    if info_tmp:
        viewer_username = info_tmp.get("username")

# Fallback: if no detected viewer_username we keep None (non-authenticated viewer)
# Build pages list, include Admin Portal only if detected username is in ADMIN_USERS
sidebar_pages = [
    "Home",
    "Chatbot",
    "Chat Support",
    "Ticket Classifier",
    "Troubleshoot",
    "Application Installer",
    "Proactive Health Agent",
    "System Information",
]
if viewer_username and viewer_username in ADMIN_USERS:
    sidebar_pages.append("Admin Portal")

# Sidebar logo (optional)
logo_path = os.path.join("src", "sys-ai", "images", "inf_logo.png")
if os.path.exists(logo_path):
    st.sidebar.image(logo_path)
else:
    st.sidebar.write("🧠 SYS AI Support System")

st.sidebar.title("🔍 Navigation")
page = st.sidebar.radio("Go to", sidebar_pages)

# --------------------------
# Helper: fetch agents list (reuse)
# --------------------------
# fetch_agents() defined above

# --------------------------
# HOME PAGE
# --------------------------
if page == "Home":
    st.title("🛠️ SYS AI- Powered L1 Support Engineer")
    st.markdown(
        """
        Welcome to the **AI-Powered IT Support Assistant**!  
        This tool automates **L1 support tasks**, provides **system insights**, and enhances troubleshooting efficiency.
        """
    )

    # Fetch all agents
    agents = fetch_agents()

    # Identify agent
    detected_agent = detect_agent_by_identity(
        param_agent=st.query_params.get("agent_id"),
        client_ip=get_client_ip(),
        local_hostname=socket.gethostname(),
        agents=agents
    )

    if not detected_agent:
        st.warning(
            """
            ❌ No SysAI Agent detected for your device.  
            Please run **SysAI-Agent.exe** or open:  
            `?agent_id=YOUR_AGENT_ID`
            """
        )
        st.stop()

    agent_id = detected_agent["agent_id"]
    st.session_state["current_user_agent"] = agent_id
    st.success(f"🖥 Connected as Agent: **{agent_id}**")

    # Load backend data
    info = get_agent_info(agent_id)
    if not info:
        st.error("❌ Unable to load device details from backend.")
        st.stop()

    st.session_state["current_user"] = info.get("username", agent_id)

    # ------------------------------
    # FIX: Correct IP shown on homepage
    # ------------------------------
    correct_ip = info.get("ip_address", "Unknown")
    correct_hostname = info.get("hostname", "Unknown")

    st.write(f"🌐 **Your IP Address:** {correct_ip}")
    st.write(f"💻 **Your Hostname:** {correct_hostname}")

    # ------------------------------
    # DEVICE INFORMATION UI
    # ------------------------------
    st.subheader("🧰 Device Information")

    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Hostname:** {info.get('hostname', 'N/A')}")
        st.write(f"**Username:** {info.get('username', 'N/A')}")
        st.write(f"**Operating System:** {info.get('os', 'N/A')}")
    with col2:
        st.write(f"**IP Address:** {info.get('ip_address', 'N/A')}")
        st.write(f"**Manufacturer:** {info.get('device_info', {}).get('manufacturer', 'N/A')}")
        st.write(f"**Processor:** {info.get('device_info', {}).get('processor', 'N/A')}")

    st.markdown("---")

    # ------------------------------
    # SYSTEM HEALTH (BACKEND METRICS)
    # ------------------------------
    metrics = info.get("metrics", {})
    ram_usage = metrics.get("ram_usage", 0)
    cpu_usage = metrics.get("cpu_usage", 0)
    disk_usage = metrics.get("disk_usage", 0)

    st.subheader("🔍 System Health Overview")

    st.markdown(f"""
        <div class="row text-center">
            <div class="col-md-4" style="max-width:33%; display:inline-block; vertical-align:top;">
                <div class="usage-card" style="padding:12px;">
                    <h5 style="margin-top:6px;">💾 RAM</h5>
                    <div class="gauge-container ram" style="width:110px; height:110px; margin:12px auto;">
                        <span class="gauge-text">{ram_usage}%</span>
                    </div>
                </div>
            </div>
            <div class="col-md-4" style="max-width:33%; display:inline-block; vertical-align:top;">
                <div class="usage-card" style="padding:12px;">
                    <h5 style="margin-top:6px;">💻 CPU</h5>
                    <div class="gauge-container cpu" style="width:110px; height:110px; margin:12px auto;">
                        <span class="gauge-text">{cpu_usage}%</span>
                    </div>
                </div>
            </div>
            <div class="col-md-4" style="max-width:33%; display:inline-block; vertical-align:top;">
                <div class="usage-card" style="padding:12px;">
                    <h5 style="margin-top:6px;">🖴 Disk</h5>
                    <div class="gauge-container disk" style="width:110px; height:110px; margin:12px auto;">
                        <span class="gauge-text">{disk_usage}%</span>
                    </div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    st.markdown(
        """
        📌 **Features:**  
        - 🔍 AI-Powered Ticket Classification  
        - 🤖 Intelligent Chatbot  
        - 📊 Log Monitoring & Anomaly Detection  
        - 🔄 Troubleshooting & Service Restart  
        - 🎟️ Admin Ticket Management  
        - 🖥 System Information Dashboard  
        - 📦 Application Installer with Admin Approval  
        - 🛡️ Proactive System Health Predictions  
        """
    )

# --------------------------
# Ticket Classifier
# --------------------------
elif page == "Ticket Classifier":
    st.title("📌 Ticket Classifier")
    st.write("Describe your IT issue below:")
    issue = st.text_area("🔍 IT Issue", height=150, placeholder="Enter issue details...")
    if st.button("🚀 Classify & Create Ticket"):
        if issue.strip():
            category = classify_ticket(issue)
            new_ticket = save_ticket(issue)
            # Ensure created ticket has the correct username/hostname if we detected agent
            detected_agent_id = st.session_state.get("current_user_agent")
            if detected_agent_id:
                # patch the ticket file to override username/hostname to agent's username/hostname
                try:
                    with open("tickets.json", "r", encoding="utf-8") as tf:
                        tickets = json.load(tf)
                    # find the ticket we just created
                    for t in tickets[::-1]:
                        if t.get("ticket_id") == new_ticket.get("ticket_id"):
                            info_local = get_agent_info(detected_agent_id)
                            if info_local:
                                t["username"] = info_local.get("username", t.get("username"))
                                t["hostname"] = info_local.get("hostname", t.get("hostname"))
                            break
                    with open("tickets.json", "w", encoding="utf-8") as tf:
                        json.dump(tickets, tf, indent=4)
                except Exception:
                    pass
            st.success(f"Ticket created ({new_ticket['ticket_id']}), category: {category}")
        else:
            st.warning("Please enter an issue description.")

# --------------------------
# Chatbot
# --------------------------
elif page == "Chatbot":
    st.title("💬 IT Support Chatbot")
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []
    for role, message in st.session_state["chat_history"]:
        if role == "user":
            st.chat_message("user").write(message)
        else:
            st.chat_message("assistant").write(message)
    if prompt := st.chat_input("Type your message here..."):
        st.session_state.chat_history.append(("user", prompt))
        response = get_chatbot_response(prompt, st.session_state["chat_history"])
        st.session_state.chat_history.append(("assistant", response))
        st.chat_message("assistant").write(response)

# --------------------------
# Troubleshoot
# --------------------------
elif page == "Troubleshoot":
    st.title("🔄 Troubleshoot")
    SERVICE_MAPPING = {
        "Printer Service": "Spooler",
        "Wi-Fi Service": "WlanSvc",
        "Windows Update": "wuauserv",
        "Remote Desktop": "TermService",
        "DNS Client": "Dnscache",
        "DHCP Client": "Dhcp",
        "Windows Firewall": "mpssvc",
    }
    service_choice = st.selectbox("🛠️ Select a service:", list(SERVICE_MAPPING.keys()))
    if st.button("Restart Service", use_container_width=True):
        service_name = SERVICE_MAPPING.get(service_choice)
        status_message = restart_service(service_name)
        if "✅" in status_message:
            st.success(status_message)
        elif "⚠️" in status_message:
            st.warning(status_message)
        else:
            st.error(status_message)

# --------------------------
# Admin Portal
# --------------------------
elif page == "Admin Portal":
    st.title("🎫 Admin Portal")

    # Only Admin sees this page
    if current_user not in ADMIN_USERS:
        st.error("⛔ You are not authorized to access the Admin Portal.")
        st.stop()

    st.write("Manage tickets, view devices and chat with users.")

    # ---------------------------------------------------------
    # ADMIN AGENT ID (LOCAL QUICK ASSIST LAUNCHER)
    # ---------------------------------------------------------
    ADMIN_AGENT_ID = "INL-INL-8HKKTQ2-9bbccf42"   # your admin PC agent_id

    st.markdown("### 🖥 Remote Assist (Admin Device)")

    if st.button("🟢 Launch Quick Assist on Admin Machine"):
        cmd_payload = {
            "id": f"admin-qa-{int(time.time())}",
            "type": "quick_assist"
        }

        try:
            r = requests.post(
                f"{BACKEND_URL}/api/agent/send/{ADMIN_AGENT_ID}",
                json=cmd_payload,
                timeout=5
            )

            if r.status_code == 200:
                st.success("📡 Quick Assist is launching on your Admin machine...")
            else:
                st.error(f"❌ Backend error: {r.text}")

        except Exception as e:
            st.error(f"❌ Failed to send Quick Assist command: {e}")

    # st.info("This will open Quick Assist on your Admin PC. Provide the 6-digit code to the user.")

    st.markdown("---")

    # ---------------------------------------------------------
    # CONNECTED DEVICES
    # ---------------------------------------------------------
    st.subheader("🖥 Connected Devices (Agent Systems)")
    agents = fetch_agents()
    if not agents:
        st.info("No connected agents.")
        st.stop()

    agent_names = [
        f"{a['agent_id']} — {a['hostname']} ({'Online' if a['online'] else 'Offline'})"
        for a in agents
    ]
    selected_display = st.selectbox("Select device to inspect:", agent_names)
    selected_agent = selected_display.split(" — ")[0]

    st.markdown("---")

    # ---------------------------------------------------------
    # TICKET SECTION
    # ---------------------------------------------------------
    TICKETS_FILE = "tickets.json"

    def load_tickets():
        try:
            with open(TICKETS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []

    tickets = load_tickets()

    if tickets:
        df = pd.DataFrame(tickets).sort_values(by="ticket_id", ascending=False)
        total_tickets = len(df)
        unresolved_tickets = df[df["status"] == "unresolved"].shape[0]
        pending_tickets = df[df["status"] == "pending"].shape[0]
        resolved_tickets = df[df["status"] == "resolved"].shape[0]

        stat_css = """
        <style>
            .stat-card { backdrop-filter: blur(10px); border-radius: 15px; padding: 20px; text-align: center; color: white; font-weight: bold; box-shadow: 5px 5px 15px rgba(0,0,0,0.2); }
            .stat-circle { width: 60px; height: 60px; border-radius: 50%; display:flex; align-items:center; justify-content:center; font-size:24px; margin:10px auto; }
            .blue{background:#007BFF;} .yellow{background:#FFC107;} .red{background:#DC3545;} .green{background:#28A745;}
        </style>
        """
        st.markdown(stat_css, unsafe_allow_html=True)

        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"<div class='stat-card blue'><h4>Total</h4><div class='stat-circle'>{total_tickets}</div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='stat-card yellow'><h4>Pending</h4><div class='stat-circle'>{pending_tickets}</div></div>", unsafe_allow_html=True)
        c3.markdown(f"<div class='stat-card red'><h4>In Progress</h4><div class='stat-circle'>{unresolved_tickets}</div></div>", unsafe_allow_html=True)
        c4.markdown(f"<div class='stat-card green'><h4>Resolved</h4><div class='stat-circle'>{resolved_tickets}</div></div>", unsafe_allow_html=True)

        st.markdown("---")

        # Ticket table
        gb = GridOptionsBuilder.from_dataframe(df)
        gb.configure_pagination(enabled=True)
        gb.configure_side_bar()
        gb.configure_selection(selection_mode="single")
        gb.configure_column(
            "status",
            editable=True,
            cellEditor="agSelectCellEditor",
            cellEditorParams={"values":["unresolved", "pending", "resolved"]},
        )

        grid = AgGrid(df, gridOptions=gb.build(), height=300, theme="streamlit")
        updated_df = grid["data"]

        # Update JSON when changed
        for _, row in updated_df.iterrows():
            orig = df[df["ticket_id"] == row["ticket_id"]]
            if not orig.empty and orig.iloc[0]["status"] != row["status"]:
                for t in tickets:
                    if t["ticket_id"] == row["ticket_id"]:
                        t["status"] = row["status"]
                with open(TICKETS_FILE, "w") as f:
                    json.dump(tickets, f, indent=4)
                st.success(f"Updated ticket {row['ticket_id']} → {row['status']}")

        st.markdown("---")
        admin_approval_ui()

    else:
        st.warning("No tickets found.")

    st.markdown("---")

    # ---------------------------------------------------------
    # DEVICE INFO
    # ---------------------------------------------------------
    try:
        info_res = requests.get(f"{BACKEND_URL}/api/agent/info/{selected_agent}", timeout=5)
        if info_res.status_code != 200:
            st.error("Unable to fetch system info.")
            st.stop()
        device_info = info_res.json()
    except Exception as e:
        st.error(f"Error fetching info: {e}")
        st.stop()

    st.subheader("🧩 Device System Information")
    st.json(device_info)

    st.markdown("---")

    # ---------------------------------------------------------
    # CHAT WITH USER
    # ---------------------------------------------------------
    st.subheader(f"💬 Chat with User ({selected_agent})")

    conv = get_chat_for_user(selected_agent)

    if conv:
        for msg in conv:
            if msg["role"] == "user":
                st.chat_message("user").write(msg["message"])
            else:
                st.chat_message("assistant").write("🛠 IT: " + msg["message"])
    else:
        st.info("No messages exchanged yet.")

    reply_key = f"reply_{selected_agent}"
    if reply_key not in st.session_state:
        st.session_state[reply_key] = ""

    def send_reply():
        text = st.session_state[reply_key].strip()
        if text:
            add_message(selected_agent, "it", text)
            st.session_state[reply_key] = ""
            st.rerun()

    col1, col2 = st.columns([8, 1])
    col1.text_input("Reply to user:", key=reply_key)
    col2.button("Send", on_click=send_reply)

    
# --------------------------
# Proactive Health Agent page
# --------------------------
elif page == "Proactive Health Agent":
    st.title("🩺 Proactive System Health Agent")
    agent_id = st.session_state.get("current_user_agent")
    if not agent_id:
        st.warning("⚠ Please open the Home page first so your device can be identified.")
        st.stop()

    info = get_agent_info(agent_id)
    if not info:
        st.error("❌ Device data not available. Is the agent running?")
        st.stop()

    st.subheader("📊 Latest System Health Report")
    # The backend presently stores raw metrics. If you'd like predictions saved in backend,
    # implement an endpoint and have the agent send them. For now we run local model analysis.
    try:
        summary, ai = system_health_prediction()
        st.json(summary)
        st.subheader("🤖 AI Recommendation")
        st.write(ai)
    except Exception as e:
        st.error(f"Health model failed: {e}")

# About Company - omitted (you commented it out in original)
elif page == "Application Installer":
    application_installer_ui()

# --------------------------
# System Information
# --------------------------
elif page == "System Information":
    st.title("🖥️ System Information Overview")
    # detect agent id from URL/session
    agent_id = None
    if st.query_params and "agent_id" in st.query_params:
        tmp = st.query_params.get("agent_id")
        agent_id = tmp[0] if isinstance(tmp, list) else tmp
    if not agent_id:
        agent_id = st.session_state.get("current_user_agent")

    if not agent_id:
        st.warning("⚠ Device not detected. Please open the Home page first.")
        st.stop()

    info = get_agent_info(agent_id)
    if not info:
        st.error("❌ Device not found in backend database.")
        st.stop()

    st.subheader("🧰 Device Overview")
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Hostname:** {info.get('hostname')}")
        st.write(f"**Username:** {info.get('username')}")
        st.write(f"**Operating System:** {info.get('os')}")
    with col2:
        st.write(f"**IP Address:** {info.get('ip_address')}")
        st.write(f"**Manufacturer:** {info.get('device_info', {}).get('manufacturer', 'N/A')}")
        st.write(f"**Processor:** {info.get('device_info', {}).get('processor', 'N/A')}")
    st.markdown("---")
    st.subheader("📊 Live System Metrics")
    metrics = info.get("metrics", {})
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("CPU Usage", f"{metrics.get('cpu_usage', 0)}%")
    with c2:
        st.metric("RAM Usage", f"{metrics.get('ram_usage', metrics.get('ram_percent',0))}%")
    with c3:
        st.metric("Disk Usage", f"{metrics.get('disk_usage', metrics.get('disk_percent',0))}%")
    st.markdown("---")
    st.subheader("📂 Full System Report")
    st.json(info)

# --------------------------
# Chat Support page
# --------------------------
elif page == "Chat Support":
    st.title("Live Chat — IT Support")

    # FLOATING QUICK ASSIST BUTTON (only on Chat Support)
    qa_clicked = st.button("🔗 Give Remote Access", key="quick_assist_float")

    # --------------------------
    # 1) Robust Agent Detection
    # --------------------------
    user_ip = get_client_ip()
    param_agent = None

    # Read agent_id from URL
    if st.query_params and "agent_id" in st.query_params:
        tmp = st.query_params.get("agent_id")
        param_agent = tmp[0] if isinstance(tmp, list) else tmp

    # Load backend devices
    agents = fetch_agents()

    detected_agent = None

    # Priority 1: URL param
    if param_agent:
        for a in agents:
            if a.get("agent_id") == param_agent:
                detected_agent = a
                break

    # Priority 2: IP match
    if not detected_agent and user_ip:
        for a in agents:
            if a.get("ip_address") == user_ip:
                detected_agent = a
                break

    # Priority 3: Session saved agent (most reliable)
    if not detected_agent and "current_user_agent" in st.session_state:
        for a in agents:
            if a.get("agent_id") == st.session_state["current_user_agent"]:
                detected_agent = a
                break

    # Priority 4: FINAL fallback → find ANY agent matching hostname from browser open
    if not detected_agent:
        try:
            local_host = socket.gethostname().lower()
            for a in agents:
                if a.get("hostname", "").lower() == local_host:
                    detected_agent = a
                    break
        except:
            pass

    # If STILL NOT detected → instruct user
    if not detected_agent:
        st.warning("""
        ❌ User not detected.

        Please:
        1️⃣ Make sure SysAI-Agent.exe is running  
        2️⃣ OR open the app using the link:  
        👉 **http://172.16.1.41:8501/?agent_id=YOUR_AGENT_ID**
        """)
        st.stop()

    # Safe: agent identified
    agent_id = detected_agent["agent_id"]
    st.session_state["current_user_agent"] = agent_id

    # --------------------------
    # 2) Quick Assist Trigger
    # --------------------------
    if qa_clicked:
        import uuid
        cmd_id = str(uuid.uuid4())
        payload = {
    "type": "quick_assist",
    "id": f"qa-{int(time.time())}"
}

        try:
            r = requests.post(f"{BACKEND_URL}/api/agent/send/{agent_id}", json=payload, timeout=5)
            if r.status_code == 200:
                st.success("📡 Quick Assist request sent. User's device will open Quick Assist shortly.")
            else:
                st.error(f"Backend error: {r.text}")
        except Exception as e:
            st.error(f"Quick Assist send failed: {e}")

    # --------------------------
    # 3) Load username + chat
    # --------------------------
    try:
        info = requests.get(f"{BACKEND_URL}/api/agent/info/{agent_id}", timeout=5).json()
    except:
        info = {}

    username = info.get("username", agent_id)
    st.session_state["current_user"] = username

    st.markdown(f"### 👤 Chat as: **{username}** ({agent_id})")

    # --------------------------
    # 4) Display Conversation
    # --------------------------
    convo = get_chat_for_user(agent_id)

    if convo:
        for msg in convo:
            if msg["role"] == "user":
                st.chat_message("user").write(msg["message"])
            else:
                st.chat_message("assistant").write("🛠 IT Team: " + msg["message"])
    else:
        st.info("No messages yet.")

    # --------------------------
    # 5) Send New Message
    # --------------------------
    if "chat_input" not in st.session_state:
        st.session_state.chat_input = ""

    def send_message():
        msg = st.session_state.chat_input.strip()
        if msg:
            add_message(agent_id, "user", msg)
            st.session_state.chat_input = ""
            st.rerun()

    msg_col, send_col = st.columns([8, 1])
    msg_col.text_input("Message to IT", key="chat_input")
    send_col.button("Send", on_click=send_message)

    # --------------------------
    # 6) Ticket Escalation
    # --------------------------
    st.markdown("---")
    if st.button("Escalate to IT — Create Ticket"):
        try:
            issue_text = "User requested escalation."
            if convo:
                for m in reversed(convo):
                    if m["role"] == "user":
                        issue_text = m["message"]
                        break

            new_ticket = save_ticket(issue_text)
            st.success(f"Ticket Created: {new_ticket.get('ticket_id')}")

            add_message(agent_id, "user", f"Ticket Created: {new_ticket.get('ticket_id')}")
            st.rerun()

        except Exception as e:
            st.error(f"Ticket creation failed: {e}")