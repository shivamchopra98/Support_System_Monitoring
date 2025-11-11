import json
import os
import streamlit as st
import subprocess

APPLICATIONS_FILE = "C:/Users/infolabsuser/Desktop/sys-ai/sys-ai/applications.json"
APP_FOLDER = "downloads"  # Permanent app folder

# Load applications from JSON
def load_applications():
    try:
        with open(APPLICATIONS_FILE, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

# Save applications to JSON
def save_applications(applications):
    with open(APPLICATIONS_FILE, "w") as file:
        json.dump(applications, file, indent=4)

# Scan folder for .exe applications and add them to JSON
def scan_and_update_apps():
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

# UI for Application Installer
def application_installer_ui():
    st.title("📦 Application Installer")
    st.write("Select an application and request admin approval.")

    scan_and_update_apps()  # Update app list

    applications = load_applications()
    pending_apps = [app["name"] for app in applications if app["status"] == "pending"]

    if not pending_apps:
        st.warning("No applications available for request.")
        return

    selected_app = st.selectbox("Select an application:", pending_apps)

    if st.button("🔑 Request Admin Approval"):
        for app in applications:
            if app["name"] == selected_app:
                st.success(f"Approval request sent for {selected_app}.")
                save_applications(applications)
                st.rerun()

    # Show approved apps ready for installation
    approved_apps = [app for app in applications if app["approved"] and app["status"] == "pending"]

    if approved_apps:
        st.subheader("✅ Approved Applications for Installation")
        install_app = st.selectbox("Select an app to install:", [app["name"] for app in approved_apps])

        if st.button("🚀 Install Application"):
            for app in applications:
                if app["name"] == install_app:
                    if install_application(app["path"]):
                        app["status"] = "installed"
                        save_applications(applications)
                        st.success(f"{install_app} installed successfully!")
                        st.rerun()
                    else:
                        st.error(f"Installation failed for {install_app}.")

# Function to install application
def install_application(app_path):
    try:
        subprocess.run([app_path, "/S"], check=True)  # Silent install mode
        return True
    except Exception as e:
        st.error(f"Error installing {app_path}: {e}")
        return False

# UI for Admin Approval
def admin_approval_ui():
    st.title("🔑 Admin Approval Portal")
    print(load_applications())
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
