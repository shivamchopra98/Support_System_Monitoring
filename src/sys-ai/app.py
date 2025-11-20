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

def set_custom_css():
    st.markdown("""
<style>

 /* ==========================================================
    EXISTING GLOBAL STYLES (KEPT INTACT)
 ========================================================== */
#chat-float-btn, #admin-float-btn { display: none !important; }
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
.floating-btn:hover { background: #144f8a; }

body { background-color: #fff; color: #2b3b99; }
.stApp { background-color: #fff; }

[data-testid="stSidebar"] {
    background-image: linear-gradient(45deg, #2d3695, #1a69bb);
    padding: 20px;
}
[data-testid="stSidebar"] * { color: #fff !important; }


 /* ==========================================================
    MODERN CHAT UI — WHATSAPP A2 THEME
 ========================================================== */
.chat-container {
    max-height: 520px;
    overflow-y: auto;
    padding: 16px;
    background: #f7f9fc;
    border-radius: 12px;
    border: 1px solid #e6eefc;
    margin-bottom: 12px;
    scroll-behavior: smooth;
}

/* LEFT BUBBLE (IT) */
.chat-bubble-it {
    background: #eef2f5;
    color: #111827;
    padding: 10px 14px;
    border-radius: 14px;
    max-width: 72%;
    margin-right: auto;
    margin-bottom: 8px;
    box-shadow: 0 2px 6px rgba(2, 6, 23, 0.06);
}

/* RIGHT BUBBLE (USER) — A2 Green */
.chat-bubble-user {
    background: #1f9a4a; /* Professional green */
    color: #fff;
    padding: 10px 14px;
    border-radius: 14px;
    max-width: 72%;
    margin-left: auto;
    margin-bottom: 8px;
    box-shadow: 0 2px 8px rgba(31,154,74,0.12);
}

/* TIMESTAMPS */
.chat-timestamp {
    font-size: 11px;
    color: #6b7280;
    margin-top: 4px;
    margin-bottom: 8px;
}
.chat-timestamp-left { text-align: left; }
.chat-timestamp-right { text-align: right; }

/* TICKS (Seen/Delivered) */
.tick {
    font-size: 12px;
    margin-left: 8px;
    vertical-align: middle;
    color: #93a0b5; /* light grey */
}
.tick.delivered { color: #93a0b5; }
.tick.read { color: #2b9cf3; } /* Blue WhatsApp tick */


/* EMPTY MESSAGE BOX */
.chat-empty {
    padding: 12px;
    background: #f0f7ff;
    border-radius: 8px;
    color: #4b5563;
    text-align: center;
    border: 1px solid #dbeafe;
}


/* ==========================================================
    TYPING INDICATOR
 ========================================================== */
.typing {
    display:inline-block;
    padding: 8px 12px;
    background:#eef2f5;
    border-radius: 12px;
    margin: 6px 0;
    color:#6b7280;
    font-style:italic;
}

/* Animated dots */
.typing-dots {
    display:inline-block;
    vertical-align: middle;
    margin-left: 8px;
}
.typing-dots span {
    display:inline-block;
    width:6px;
    height:6px;
    background:#9aa6b2;
    border-radius:50%;
    margin:0 2px;
    opacity:0.3;
    animation: blink 1s infinite;
}
.typing-dots span:nth-child(2){ animation-delay: .15s; }
.typing-dots span:nth-child(3){ animation-delay: .3s; }

@keyframes blink {
    0% { opacity:0.3; transform: translateY(0); }
    50% { opacity:1; transform: translateY(-3px); }
    100% { opacity:0.3; transform: translateY(0); }
}


/* ==========================================================
    INPUT + SEND BUTTON FIX (PERFECT ALIGNMENT)
 ========================================================== */
.chat-input-row {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    margin-top: 10px;
}

/* INPUT BOX FIX */
.chat-input-row div[data-testid="stTextInput"] input {
    height: 48px !important;
    padding: 12px 14px !important;
    background: #f1f5f9 !important;
    border-radius: 12px !important;
    border: 1px solid #e6eefc !important;
    font-size: 16px !important;
}

/* SEND BUTTON FIX */
.chat-input-row div[data-testid="stButton"] button {
    height: 48px !important;
    padding: 0 26px !important;
    border-radius: 12px !important;
    font-size: 16px !important;
    font-weight: 600 !important;
    background: #2563eb !important;
    color: white !important;
    border: none !important;
    white-space: nowrap !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;

    /* Remove blur/glow */
    box-shadow: none !important;
    filter: none !important;

    transition: background 0.15s ease-in-out;
}

/* HOVER — NO GLOW, NO BLUR */
.chat-input-row div[data-testid="stButton"] button:hover {
    background: #1e54c9 !important;
    box-shadow: none !important;
    filter: none !important;
}

/* ACTIVE */
.chat-input-row div[data-testid="stButton"] button:active {
    transform: translateY(1px);
    box-shadow: none !important;
}

/* Prevent shrinking */
.chat-input-row div[data-testid="stButton"] { flex-shrink: 0; }


/* ==========================================================
    RESPONSIVE BEHAVIOR
 ========================================================== */
@media (max-width: 800px) {
    .chat-bubble-it, .chat-bubble-user {
        max-width: 90%;
        font-size: 14px;
    }
    .chat-container { padding: 10px; }
}

</style>
""", unsafe_allow_html=True)

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
    # SELECT DEVICE FIRST
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

    # ---------------------------------------------------------
    # QUICK ASSIST (LOCAL ADMIN LAUNCH)
    # ---------------------------------------------------------
    st.markdown("### 🖥 Remote Assist (Admin)")

    st.markdown("""
        <style>
            #admin-local-qa-btn {
                background-color: #28a745;
                color: white;
                padding: 12px 20px;
                border-radius: 8px;
                border: none;
                font-size: 16px;
                cursor: pointer;
                box-shadow: 0px 4px 10px rgba(0,0,0,0.2);
            }
            #admin-local-qa-btn:hover {
                background-color: #218838;
            }
        </style>

        <button id="admin-local-qa-btn">🟢 Launch Quick Assist (Admin)</button>

        <script>
            document.getElementById("admin-local-qa-btn").onclick = function() {
                window.location.href = "ms-quickassist:";
            }
        </script>
    """, unsafe_allow_html=True)

    st.info("Click the button above to launch Quick Assist on your computer.\nProvide the 6-digit code to the user to connect to their device.")

    st.markdown("---")

    # ---------------------------------------------------------
    # TICKETS SECTION
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
            cellEditorParams={"values":["unresolved", "pending", "resolved"]}
        )

        grid = AgGrid(df, gridOptions=gb.build(), height=300, theme="streamlit")
        updated_df = grid["data"]

        # Update JSON on status change
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
    # DEVICE INFO SECTION
    # ---------------------------------------------------------
    try:
        info_res = requests.get(f"{BACKEND_URL}/api/agent/info/{selected_agent}", timeout=5)
        if info_res.status_code != 200:
            st.error("Unable to fetch system information for this device.")
            st.stop()
        device_info = info_res.json()
    except Exception as e:
        st.error(f"Error fetching device info: {e}")
        st.stop()

    st.subheader("🧩 Device System Information")
    st.json(device_info)

    st.markdown("---")

    # -------------------------------
    # CHAT WITH USER (ADMIN)
    # -------------------------------
    st.subheader(f"💬 Chat with User ({selected_agent})")

    conv = get_chat_for_user(selected_agent)

    if conv:
        for msg in conv:
            timestamp = msg.get("timestamp", "")
            text = msg.get("message", "")
            status = msg.get("status", "")

            # Admin view: user messages on left, IT (admin) on right
            if msg["role"] == "user":
                st.markdown(
                    f"""
                    <div>
                        <div class="chat-bubble-it">{text}</div>
                        <div class="chat-timestamp chat-timestamp-left">{timestamp}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            else:
                # admin messages show ticks similar to user side
                tick_html = ""
                if status == "seen":
                    tick_html = '<span class="tick read">✔✔</span>'
                elif status == "delivered":
                    tick_html = '<span class="tick delivered">✔✔</span>'
                elif status == "sent":
                    tick_html = '<span class="tick delivered">✔</span>'

                st.markdown(
                    f"""
                    <div>
                        <div class="chat-bubble-user">{text}</div>
                        <div class="chat-timestamp chat-timestamp-right">{timestamp}{tick_html}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
    else:
        st.markdown('<div class="chat-empty">No messages exchanged yet.</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # auto-scroll admin chat
    st.markdown("""
        <script>
        (function() {
            var c = document.getElementById('admin_chatbox');
            if (c) { c.scrollTop = c.scrollHeight; }
        })();
        </script>
    """, unsafe_allow_html=True)

    # Typing indicator for user typing (toggle via st.session_state["user_typing"])
    if st.session_state.get("user_typing", False):
        st.markdown("""
            <div class="typing">
                👤 User is typing
                <span class="typing-dots"><span></span><span></span><span></span></span>
            </div>
        """, unsafe_allow_html=True)

    # Reply input (keeps your logic)
    reply_key = f"reply_{selected_agent}"
    if reply_key not in st.session_state:
        st.session_state[reply_key] = ""

    def send_reply():
        text = st.session_state[reply_key].strip()
        if text:
            add_message(selected_agent, "it", text)
            st.session_state[reply_key] = ""
            st.rerun()

    st.markdown('<div class="chat-input-row">', unsafe_allow_html=True)

    col1, col2 = st.columns([9,1])
    with col1:
        st.text_input("Type your reply...", key=reply_key, label_visibility="collapsed")

    with col2:
        st.button("Send", on_click=send_reply)
    st.markdown('</div>', unsafe_allow_html=True)
    
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
    # 1) Robust Agent Detection (unchanged)
    # --------------------------
    user_ip = get_client_ip()
    param_agent = None

    if st.query_params and "agent_id" in st.query_params:
        tmp = st.query_params.get("agent_id")
        param_agent = tmp[0] if isinstance(tmp, list) else tmp

    agents = fetch_agents()
    detected_agent = None

    if param_agent:
        for a in agents:
            if a.get("agent_id") == param_agent:
                detected_agent = a
                break

    if not detected_agent and user_ip:
        for a in agents:
            if a.get("ip_address") == user_ip:
                detected_agent = a
                break

    if not detected_agent and "current_user_agent" in st.session_state:
        for a in agents:
            if a.get("agent_id") == st.session_state["current_user_agent"]:
                detected_agent = a
                break

    if not detected_agent:
        try:
            local_host = socket.gethostname().lower()
            for a in agents:
                if a.get("hostname", "").lower() == local_host:
                    detected_agent = a
                    break
        except:
            pass

    if not detected_agent:
        st.warning("""
        ❌ User not detected.

        Please:
        1️⃣ Make sure SysAI-Agent.exe is running  
        2️⃣ OR open the app using the link:  
        👉 **http://172.16.1.41:8501/?agent_id=YOUR_AGENT_ID**
        """)
        st.stop()

    agent_id = detected_agent["agent_id"]
    st.session_state["current_user_agent"] = agent_id

    # --------------------------
    # 2) Quick Assist Trigger (unchanged behavior)
    # --------------------------
    if qa_clicked:
        payload = {"type": "quick_assist", "id": f"qa-{int(time.time())}"}
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
    # 4) Display Conversation (modern UI)
    # --------------------------
    convo = get_chat_for_user(agent_id)

    # chat container + auto-scroll script

    if convo:
        for msg in convo:
            timestamp = msg.get("timestamp", "")
            text = msg.get("message", "")
            status = msg.get("status", "")  # optional: 'sent', 'delivered', 'seen'

            # decide tick html
            tick_html = ""
            if msg.get("role") == "user":
                # show ticks for user's messages
                if status == "seen":
                    tick_html = '<span class="tick read">✔✔</span>'
                elif status == "delivered":
                    tick_html = '<span class="tick delivered">✔✔</span>'
                elif status == "sent":
                    tick_html = '<span class="tick delivered">✔</span>'

            if msg["role"] == "user":
                st.markdown(
                    f"""
                    <div>
                        <div class="chat-bubble-user">{text}</div>
                        <div class="chat-timestamp chat-timestamp-right">{timestamp}{tick_html}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f"""
                    <div>
                        <div class="chat-bubble-it">{text}</div>
                        <div class="chat-timestamp chat-timestamp-left">{timestamp}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
    else:
        st.markdown('<div class="chat-empty">No messages yet.</div>', unsafe_allow_html=True)

    # Typing indicator (IT team typing) - toggled by st.session_state["it_typing"]
    if st.session_state.get("it_typing", False):
        st.markdown("""
            <div class="typing">
                🛠 IT Team is typing
                <span class="typing-dots"><span></span><span></span><span></span></span>
            </div>
            """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # small JS to auto-scroll to bottom (runs after render)
    st.markdown("""
        <script>
        (function() {
            var c = document.getElementById('chatbox');
            if (c) { c.scrollTop = c.scrollHeight; }
        })();
        </script>
    """, unsafe_allow_html=True)

    # --------------------------
    # 5) Send New Message (keeps your logic)
    # --------------------------
    if "chat_input" not in st.session_state:
        st.session_state.chat_input = ""

    def send_message():
        msg = st.session_state.chat_input.strip()
        if msg:
            add_message(agent_id, "user", msg)
            st.session_state.chat_input = ""
            st.rerun()

    # aligned input + send
    st.markdown('<div class="chat-input-row">', unsafe_allow_html=True)

    col1, col2 = st.columns([9,1])

    with col1:
        st.text_input("Type your message...", key="chat_input", label_visibility="collapsed")

    with col2:
        st.button("Send", on_click=send_message)

    st.markdown('</div>', unsafe_allow_html=True)

    # --------------------------
    # 6) Ticket Escalation (unchanged)
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