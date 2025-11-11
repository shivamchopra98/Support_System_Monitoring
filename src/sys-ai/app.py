import json
import streamlit as st
from modules.ticket_classifier import classify_ticket, save_ticket
from modules.chatbot import get_chatbot_response
from modules.log_monitoring import monitor_logs
from modules.auto_troubleshoot import restart_service
from modules.about_company import about_company_ui
from modules.application_installer import application_installer_ui, admin_approval_ui
from modules.proactive_health import system_health_prediction
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode
import pandas as pd
import psutil
import shutil
import time
import os
TICKETS_FILE = "tickets.json"



# Function to load tickets
def load_tickets():
    try:
        with open(TICKETS_FILE, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        return []

# Function to update ticket status in JSON
def update_ticket_status(ticket_id, new_status):
    tickets = load_tickets()
    for ticket in tickets:
        if ticket["ticket_id"] == ticket_id:
            ticket["status"] = new_status
            break
    with open(TICKETS_FILE, "w") as file:
        json.dump(tickets, file, indent=4)

# Customizing Streamlit page
st.set_page_config(page_title="SYS AI - L1 Support", layout="wide")
logo_path = "images/inf_logo.png"
if os.path.exists(logo_path):
    st.sidebar.image(logo_path)
else:
    st.sidebar.write("🧠 SYS AI Support System")
# Sidebar for Navigation
st.sidebar.title("🔍 Navigation")
page = st.sidebar.radio(
    "Go to",
    ["Home",  "Chatbot", "Ticket Classifier", "Log Monitoring", "Troubleshoot", "About Company", "Application Installer",  "Admin Portal", ]
)

def set_custom_css():
    st.markdown(
        f"""
    
       <style>
        body {{
            background-color: #fff; /* Light Beige */
            color: #2b3b99; /* Dark Teal */
        }}
        .stApp {{
            background-color: #fff;
        }}
        [data-testid="stSidebar"] {{
            background-image: linear-gradient(45deg, #2d3695,#2d3695,#1a69bb,#1a69bb);
            padding: 20px;
        }}
        [data-testid="stSidebar"] * {{
            color: #fff !important;
        }}
        .ticket-card {{
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
            box-shadow: 2px 2px 10px rgba(0, 0, 0, 0.1);
        }}
        .resolved {{
            border-left: 5px solid green;
            background-color: #d4edda;
        }}
        .unresolved {{
            border-left: 5px solid red;
            background-color: #f8d7da;
        }}
        .btn-resolve {{
            background-color: #F4A261 !important;
            border: none;
            color: #2b3b99 !important;
            font-weight: bold;
        }}
        .btn-resolve:hover {{
            background-color: #E76F51 !important;
        }}
    </style>
        """,
        unsafe_allow_html=True
    )

set_custom_css()


def get_system_info():
    # RAM details
    ram = psutil.virtual_memory()
    ram_total = ram.total / (1024 ** 3)  # Convert to GB
    ram_used = ram.used / (1024 ** 3)
    
    # Disk details
    disk_info = {}
    for partition in psutil.disk_partitions():
        try:
            usage = shutil.disk_usage(partition.mountpoint)
            disk_info[partition.device] = {
                "free": usage.free / (1024 ** 3),   # Convert to GB
                "total": usage.total / (1024 ** 3)
            }
        except PermissionError:
            disk_info[partition.device] = {"error": "Drive not accessible"}

    # CPU details
    cpu_cores = psutil.cpu_count(logical=True)
    cpu_usage = psutil.cpu_percent(interval=1)

    # Last shutdown time (Uptime)
    uptime_seconds = time.time() - psutil.boot_time()
    last_shutdown_days = round(uptime_seconds / 86400, 1)

    return ram_total, ram_used, disk_info, cpu_cores, cpu_usage, last_shutdown_days

# Add System Information to Sidebar
st.sidebar.title("🖥️ System Information")

ram_total, ram_used, disk_info, cpu_cores, cpu_usage, last_shutdown_days = get_system_info()

st.sidebar.markdown(f"**RAM:** {ram_used:.2f} GB / {ram_total:.2f} GB")

# Show each disk's space
for disk, details in disk_info.items():
    if "error" in details:
        st.sidebar.markdown(f"{disk}: {details['error']}")
    else:
        st.sidebar.markdown(f"{disk}: Free: {details['free']:.2f} GB / Total: {details['total']:.2f} GB")

st.sidebar.markdown(f"**CPU:** Cores: {cpu_cores}, Usage: {cpu_usage:.1f}%")
st.sidebar.markdown(f"**Last Shutdown:** {last_shutdown_days} days ago")

# Home Page
if page == "Home":
    st.title("🛠️ SYS AI- Powered L1 Support Engineer")
    st.markdown(
        """
        Welcome to the **AI-Powered IT Support Assistant**!  
        This tool automates **L1 support tasks**, provides **system insights**, and enhances troubleshooting efficiency.  

      
        """
    )

    # st.title("📊 Proactive System Health Predictions")

    # Load Bootstrap & Custom Styles
    st.markdown("""
        <link rel="stylesheet" 
              href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
        <style>
            body {
                background-color: #fff; 
                color: #2b3b99;
            }
            .stApp {
                background-color: #fff;
            }
            [data-testid="stSidebar"] {
                background-color:background-image: linear-gradient(45deg, #2d3695, #1a69bb);
                padding: 20px;
                box-shadow: 5px 5px 15px rgba(0, 0, 0, 0.3);
            }
            [data-testid="stSidebar"] * {
                color: #fff !important;
            }
            
            /* 3D Neumorphic Cards */
            .usage-card {
                background: #E3E3E3;
                border-radius: 20px;
                padding: 20px;
                text-align: center;
                box-shadow: 8px 8px 16px #b8b8b8, -8px -8px 16px #ffffff;
                transition: all 0.3s ease-in-out;
            }
            .usage-card:hover {
                box-shadow: 4px 4px 8px #b8b8b8, -4px -4px 8px #ffffff;
                transform: scale(1.05);
            }

            /* Circular Progress Gauges */
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
            
            /* Dynamic colors */
            .ram { background: #4CAF50; }  /* Green */
            .cpu { background: #FFC107; }  /* Yellow */
            .disk { background: #F44336; } /* Red */

            /* Status Cards */
            .status-good {
                background-color: #D4EDDA; /* Light Green */
                border-left: 5px solid green;
                padding: 15px;
                border-radius: 10px;
                box-shadow: 5px 5px 15px rgba(0, 0, 0, 0.2);
            }
            .status-warning {
                background-color: #FFF3CD; /* Light Yellow */
                border-left: 5px solid orange;
                padding: 15px;
                border-radius: 10px;
                box-shadow: 5px 5px 15px rgba(0, 0, 0, 0.2);
            }
            .status-critical {
                background-color: #F8D7DA; /* Light Red */
                border-left: 5px solid red;
                padding: 15px;
                border-radius: 10px;
                box-shadow: 5px 5px 15px rgba(0, 0, 0, 0.2);
            }
        </style>
    """, unsafe_allow_html=True)

    # Fetch Predictions
    predictions = system_health_prediction()
    ram_usage = predictions["ram"]
    cpu_usage = predictions["cpu"]
    disk_usage = predictions["disk"]

    if not predictions:
        st.warning("No predictions available.")
    else:
        st.subheader("🔍 System Health Overview")

        # Displaying 3D Neumorphic Cards with Colored Gauges
        st.markdown(f"""
            <div class="row text-center">
                <div class="col-md-4">
                    <div class="usage-card">
                        <h5>💾 RAM Usage</h5>
                        <div class="gauge-container ram">
                            <span class="gauge-text">{ram_usage}%</span>
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="usage-card">
                        <h5>💻 CPU Usage</h5>
                        <div class="gauge-container cpu">
                            <span class="gauge-text">{cpu_usage}%</span>
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="usage-card">
                        <h5>🖴 Disk Usage</h5>
                        <div class="gauge-container disk">
                            <span class="gauge-text">{disk_usage}%</span>
                        </div>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        # Display System Health Status
        status_class = "status-good" if predictions["status"] == "Good" else "status-warning" if predictions["status"] == "Warning" else "status-critical"

        st.markdown(f"""
            <div class="mt-4 {status_class}">
                <h4><strong>🩺 Health Status:</strong> {predictions['status']}</h4>
                <p><strong>Prediction:</strong> {predictions['prediction']}</p>
            </div>
        """, unsafe_allow_html=True)
        st.markdown("---")
        st.markdown(
        """
        
        📌 **Features:**  
        - **🔍 AI-Powered Ticket Classification** - Automatically categorize and prioritize tickets.  
        - **🤖 Intelligent Chatbot** - AI-driven assistant for quick issue resolution.  
        - **📊 Log Monitoring & Anomaly Detection** - Detects unusual system behavior in real-time.  
        - **🔄 Troubleshooting & Service Restart** - Identifies and restarts faulty services.  
        - **🎟️ Admin Ticket Management** - Track, update, and resolve IT support tickets.  
        - **🖥️ System Information Dashboard** - View real-time CPU, RAM, Disk, and last shutdown details.  
        - **📦 Application Installer with Admin Approval** - Manage and install applications securely.  
        - **🛡️ Proactive System Health Predictions** - AI-powered predictive analytics to prevent failures.  

        Use the **sidebar** to navigate between different sections. 🚀  
        """
    )

elif page == "Ticket Classifier":
    st.title("📌 Ticket Classifier")

    st.markdown(
        """
        <style>
        /* Background */
        .main {
            background: linear-gradient(135deg, #2b3b99, #2b3b99);
            padding: 20px;
            border-radius: 12px;
        }

        /* Glassmorphism Effect */
        .glass-card {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(15px);
            -webkit-backdrop-filter: blur(15px);
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0px 4px 15px rgba(255, 255, 255, 0.1);
            transition: transform 0.3s ease-in-out;
        }
        .glass-card:hover {
            transform: scale(1.02);
            box-shadow: 0px 6px 20px rgba(255, 255, 255, 0.15);
        }

        /* Input Box */
        .stTextArea textarea {
            font-size: 16px !important;
            border-radius: 12px !important;
            border: 2px solid #008AFF !important;
            background: rgba(255, 255, 255, 0.2) !important;
            color: black !important;
            padding: 12px !important;
        }

        /* Button Styling */
        .stButton>button {
            background: #2b3b99 !important;
            color: #fff !important;
            font-size: 18px !important;
            font-weight: bold;
            border-radius: 10px !important;
            padding: 12px 24px !important;
            transition: 0.3s;
            box-shadow: 0px 4px 12px white;
        }
        .stButton>button:hover {
            transform: scale(1.05);
            box-shadow: 0px 6px 15px #fff;
        }

        /* Ticket Style */
        .ticket-box {
            background-image: linear-gradient(90deg, #7df0bc 2%, #e9e6e6 10%);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            color: black;
            padding: 20px;
            border-radius: 15px;
            box-shadow: rgba(0, 0, 0, 0.4) 0px 2px 4px, rgba(0, 0, 0, 0.3) 0px 7px 13px -3px, rgba(0, 0, 0, 0.2) 0px -3px 0px inset;
            margin-top: 20px;
            border-left: 5px solid black;
            font-family: 'Courier New', monospace;
            text-align: center;
        }
        
       
        .ticket-id {
            font-size: 22px;
            font-weight: bold;
            color: black;
            background: rgba(255, 255, 255, 0.1);
            padding: 8px;
            border-radius: 8px;
            display: inline-block;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # UI Layout
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)

    st.write("✨ **Describe your IT issue below:**")
    issue = st.text_area("🔍 IT Issue", height=150, placeholder="Enter issue details...", label_visibility="collapsed")

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        classify_btn = st.button("🚀 Classify & Create Ticket", use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # If button is clicked
    if classify_btn:
        if issue.strip():
            category = classify_ticket(issue)
            new_ticket = save_ticket(issue)

            st.markdown(
                f"""
                <div class="ticket-box">
                    <h3>✅ Ticket Created Successfully!</h3>
                    <p>📌 <b>Category:</b> {category}</p>
                    <p>🎫 <b>Ticket ID:</b> <span class="ticket-id">{new_ticket['ticket_id']}</span></p>
                </div>
                """,
                unsafe_allow_html=True
            )
        else:
            st.warning("⚠️ Please enter an issue description.")


# Chatbot
elif page == "Chatbot":
    st.title("💬 IT Support Chatbot")
    query = st.text_input("🗣️ Ask something:")
    if st.button("Get Response", use_container_width=True):
        if query.strip():
            response = get_chatbot_response(query)
            st.info(f"🤖 **Bot:** {response}")
        else:
            st.warning("⚠️ Please enter a question.")

elif page == "Log Monitoring":
    st.title("📑 Log Monitoring")
    st.write("Check logs for errors and anomalies.")

    if st.button("Check Logs", use_container_width=True):
        logs = monitor_logs()  # Capture output
        if logs:
            st.subheader("Detected Issues")
            for log, analysis in logs:
                st.warning(f"⚠️ {log}")
                st.info(f"🤖 AI Analysis: {analysis}")
        else:
            st.success("✅ No issues found in the logs.")


# Auto Troubleshooting
elif page == "Troubleshoot":
    st.title("🔄 Troubleshoot")
    st.write("Select a service to restart automatically.")
    
    SERVICE_MAPPING = {
        "Printer Service": "Spooler",
        "Wi-Fi Service": "WlanSvc",
        "MySQL Database": "MySQL80",
        "Windows Update": "wuauserv",
        "Remote Desktop": "TermService",
        "DNS Client": "Dnscache",
        "DHCP Client": "Dhcp",
        "Windows Firewall": "mpssvc",
        "Windows Security": "wscsvc",
        "Apache Server": "Apache2.4",
        "SQL Server": "MSSQLSERVER"
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

# Admin Portal
elif page == "Admin Portal":
    st.title("🎫 Admin Portal")
    st.write("Manage and resolve tickets, and approve app installations.")

    # **Load tickets**
    tickets = load_tickets()
    if not tickets:
        st.warning("No tickets found.")
    else:
        df = pd.DataFrame(tickets)
        df = df.sort_values(by="ticket_id", ascending=False)  # Order by Descending

        # **Ticket Statistics**
        total_tickets = len(df)
        unresolved_tickets = df[df["status"] == "unresolved"].shape[0]
        pending_tickets = df[df["status"] == "pending"].shape[0]  # New: Pending Tickets
        resolved_tickets = df[df["status"] == "resolved"].shape[0]

      # **Modern 3D Cards with Colors**
        card_style = """
        <style>
            .stat-card {
                backdrop-filter: blur(10px);
                border-radius: 15px;
                padding: 20px;
                text-align: center;
                color: white;
                font-weight: bold;
                box-shadow: 5px 5px 15px rgba(0, 0, 0, 0.2);
                display: flex;
                flex-direction: column;
                align-items: center;
            }
            .stat-circle {
                width: 60px;
                height: 60px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 24px;
                font-weight: bold;
                margin-top: 10px;
                box-shadow: inset 2px 2px 5px rgba(255, 255, 255, 0.3),
                            inset -2px -2px 5px rgba(0, 0, 0, 0.3);
            }
            .blue { background: #007BFF; }
            .yellow { background: #FFC107; }
            .red { background: #DC3545; }
            .green { background: #28A745; }
        </style>
        """
        st.markdown(card_style, unsafe_allow_html=True)

        col1, col2, col3, col4 = st.columns(4)  

        with col1:
            st.markdown(f"""
                <div class="stat-card blue">
                    <h4>Total Tickets</h4>
                    <div class="stat-circle">{total_tickets}</div>
                </div>
                """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
                <div class="stat-card yellow">
                    <h4>Pending Tickets</h4>
                    <div class="stat-circle">{pending_tickets}</div>
                </div>
                """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
                <div class="stat-card red">
                    <h4>InProgress Tickets</h4>
                    <div class="stat-circle">{unresolved_tickets}</div>
                </div>
                """, unsafe_allow_html=True)

        with col4:
            st.markdown(f"""
                <div class="stat-card green">
                    <h4>Resolved Tickets</h4>
                    <div class="stat-circle">{resolved_tickets}</div>
                </div>
                """, unsafe_allow_html=True)


        st.markdown("---")

        # 🎨 **Styled Table**
        def highlight_rows(s):
            color = "#FFCCCC" if s["status"] == "unresolved" else ("#FFFF99" if s["status"] == "pending" else "#CCFFCC")
            return [f"background-color: {color}"] * len(s)

        styled_df = df.style.apply(highlight_rows, axis=1)
        
        # **Configure AgGrid**
        gb = GridOptionsBuilder.from_dataframe(df)
        gb.configure_pagination(enabled=True)  # Pagination
        gb.configure_side_bar()  # Sidebar filters
        gb.configure_selection(selection_mode="single", use_checkbox=True)

        # **Dropdown for Status Update**
        gb.configure_column(
            "status",
            editable=True,
            cellEditor="agSelectCellEditor",
            cellEditorParams={"values": ["unresolved", "pending", "resolved"]},  # Added "pending"
        )

        grid_options = gb.build()

        # **Render AgGrid with Custom Theme**
        grid_response = AgGrid(
            df,
            gridOptions=grid_options,
            height=400,
            fit_columns_on_grid_load=True,
            allow_unsafe_jscode=True,
            theme="streamlit",
        )

        # **Check if Status Changed**
        updated_df = grid_response["data"]
        for _, row in updated_df.iterrows():
            original_row = df[df["ticket_id"] == row["ticket_id"]]
            if not original_row.empty and original_row.iloc[0]["status"] != row["status"]:
                update_ticket_status(row["ticket_id"], row["status"])  # Update JSON
                st.success(f"✅ Ticket {row['ticket_id']} updated to {row['status']}!")

        st.markdown("---")

        # **Application Approval Section**
        admin_approval_ui()

# About Company
elif page == "About Company":
    about_company_ui()

elif page == "Application Installer":
    application_installer_ui()
    
# elif page == "Proactive System Health Predictions":
   
