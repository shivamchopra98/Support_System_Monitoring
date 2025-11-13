import subprocess
import json

def check_pending_updates():
    """Check if Windows has pending updates or reboot required."""
    update_status = {
        "pending_updates": False,
        "reboot_required": False,
        "update_details": []
    }

    # 1️⃣ Check if reboot is required
    try:
        reboot_cmd = r'''powershell.exe -Command "(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired' -ErrorAction SilentlyContinue) -ne $null"'''
        reboot_output = subprocess.check_output(reboot_cmd, shell=True).decode().strip()
        update_status["reboot_required"] = reboot_output == "True"
    except:
        update_status["reboot_required"] = False

    # 2️⃣ Check for installed updates (indicator of recent patches)
    try:
        updates_cmd = r'''powershell.exe -Command "Get-WmiObject -Class Win32_QuickFixEngineering | Select HotFixID,InstalledOn | ConvertTo-Json"'''
        output = subprocess.check_output(updates_cmd, shell=True).decode().strip()

        try:
            updates = json.loads(output)
            if isinstance(updates, list) and len(updates) > 0:
                update_status["pending_updates"] = False  # Installed updates list only
                update_status["update_details"] = updates
        except:
            pass

    except Exception as e:
        print("Update Check Error:", e)

    return update_status
