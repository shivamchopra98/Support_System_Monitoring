import json
import os
import streamlit as st
import subprocess

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_FOLDER = os.path.join(BASE_DIR, "downloads")  # Safer relative path
APPLICATIONS_FILE = os.path.join(BASE_DIR, "applications.json")

# --- Ensure required folders exist ---
os.makedirs(APP_FOLDER, exist_ok=True)

# --- Load Applications ---
def load_applications():
    """Load list of applications from JSON file."""
    try:
        with open(APPLICATIONS_FILE, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

# --- Save Applications ---
def save_applications(applications):
    """Save updated list of applications to JSON file."""
    with open(APPLICATIONS_FILE, "w") as file:
        json.dump(applications, file, indent=4)

# --- Scan Folder and Update JSON ---
def scan_and_update_apps():
    """Scan APP_FOLDER for .exe files and update the JSON list."""
    os.makedirs(APP_FOLDER, exist_ok=True)  # Ensure folder exists

    applications = load_applications()
    existing_apps = {app["name"]: app for app in applications}

    for file in os.listdir(APP_FOLDER):
        if file.endswith(".exe") and file not in existing_apps:
            app_path = os.path.join(APP_FOLDER, file)
            existing_apps[file] = {
                "name": file,
                "path": app_path,
                "status": "pending",
                "approved": False
            }

    save_applications(list(existing_apps.values()))

# --- App Installer UI ---
def application_installer_ui():
    """User-facing application installer interface."""
    st.title("📦 Application Installer")
    st.write("Select an application and request admin approval.")

    scan_and_update_apps()

    applications = load_applications()
    pending_apps = [app["name"] for app in applications if app["status"] == "pending"]

    if not pending_apps:
        st.warning("No applications available for request.")
        return

    selected_app = st.selectbox("Select an application:", pending_apps)

    if st.button("🔑 Request Admin Approval"):
        st.success(f"Approval request sent for {selected_app}.")
        st.rerun()

    # --- Approved Apps ---
    approved_apps = [app for app in applications if app["approved"] and app["status"] == "pending"]

    if approved_apps:
        st.subheader("✅ Approved Applications for Installation")
        install_app = st.selectbox("Select an app to install:", [app["name"] for app in approved_apps])

        if st.button("🚀 Install Application"):
            for app in applications:
                if app["name"] == install_app:
                    success = install_application(app["path"])
                    if success:
                        app["status"] = "installed"
                        save_applications(applications)
                        st.success(f"{install_app} installed successfully!")
                        st.rerun()
                    else:
                        st.error(f"Installation failed for {install_app}.")

# --- Silent Install Function ---
def install_application(app_path):
    """Performs a silent install of the selected application."""
    try:
        subprocess.run([app_path, "/S"], check=True)
        return True
    except Exception as e:
        st.error(f"Error installing {app_path}: {e}")
        return False

# --- Admin Portal ---
def admin_approval_ui():
    """Admin panel for approving pending app installations."""
    st.title("🔑 Admin Approval Portal")

    applications = load_applications()
    pending_requests = [app for app in applications if not app["approved"] and app["status"] == "pending"]

    if not pending_requests:
        st.success("No applications pending approval.")
        return

    selected_request = st.selectbox("Select an application to approve:", [app["name"] for app in pending_requests])

    if st.button("✅ Approve Application"):
        for app in applications:
            if app["name"] == selected_request:
                app["approved"] = True
                save_applications(applications)
                st.success(f"{selected_request} has been approved!")
                st.rerun()
