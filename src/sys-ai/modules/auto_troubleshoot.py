import subprocess
import time

def restart_service(service_name):
    if not service_name:
        return "❌ Error: Service name is missing or invalid!"

    try:
        # Stop the service
        stop_command = ["sc", "stop", service_name]
        stop_result = subprocess.run(stop_command, capture_output=True, text=True)

        if stop_result.returncode != 0:
            return f"⚠️ Error stopping {service_name}: {stop_result.stderr.strip() or stop_result.stdout.strip()}"

        time.sleep(3)  # ⏳ Wait for a few seconds to ensure the service stops

        # Start the service
        start_command = ["sc", "start", service_name]
        start_result = subprocess.run(start_command, capture_output=True, text=True)

        if start_result.returncode != 0:
            return f"⚠️ Error starting {service_name}: {start_result.stderr.strip() or start_result.stdout.strip()}"

        time.sleep(2)  # ⏳ Wait before checking the status

        # Check if the service is running
        check_command = ["sc", "query", service_name]
        check_result = subprocess.run(check_command, capture_output=True, text=True)

        if "RUNNING" in check_result.stdout:
            return f"✅ Successfully Restarted {service_name}"
        else:
            return f"❌ Service {service_name} failed to restart."

    except Exception as e:
        return f"⚠️ An error occurred: {str(e)}"
