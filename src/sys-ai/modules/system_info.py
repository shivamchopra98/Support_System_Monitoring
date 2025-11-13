import platform
import psutil
import subprocess
import json
import socket

def run_powershell(cmd):
    """Run PowerShell commands safely and return output."""
    result = subprocess.run(
        ["powershell", "-Command", cmd],
        capture_output=True, text=True, encoding="utf-8"
    )
    return result.stdout.strip()

def get_hostname():
    return socket.gethostname()

def get_serial_number():
    try:
        output = run_powershell("(Get-WmiObject win32_bios).SerialNumber")
        return output if output else "Unknown"
    except:
        return "Unknown"

def get_manufacturer_and_model():
    try:
        manufacturer = run_powershell("(Get-WmiObject Win32_ComputerSystem).Manufacturer")
        model = run_powershell("(Get-WmiObject Win32_ComputerSystem).Model")
        return manufacturer, model
    except:
        return "Unknown", "Unknown"

def get_os_details():
    try:
        os_info = run_powershell("Get-ComputerInfo | ConvertTo-Json")
        return json.loads(os_info)
    except:
        return {}

def detect_ssd():
    """Returns True if SSD is present, False if HDD, or 'Mixed'."""
    try:
        cmd = r"Get-PhysicalDisk | Select MediaType | ConvertTo-Json"
        output = run_powershell(cmd)
        disks = json.loads(output)

        if isinstance(disks, dict):
            disks = [disks]

        media_types = {d["MediaType"] for d in disks}

        if "SSD" in media_types and "HDD" in media_types:
            return "Mixed"
        elif "SSD" in media_types:
            return "SSD"
        elif "HDD" in media_types:
            return "HDD"
        else:
            return "Unknown"
    except:
        return "Unknown"

def get_total_ram():
    ram = psutil.virtual_memory().total / (1024 ** 3)
    return round(ram, 2)

def get_cpu_info():
    return {
        "model": platform.processor(),
        "cores": psutil.cpu_count(logical=False),
        "threads": psutil.cpu_count(logical=True),
        "architecture": platform.machine()
    }

def get_gpu_info():
    try:
        cmd = r"Get-WmiObject Win32_VideoController | Select Name | ConvertTo-Json"
        output = run_powershell(cmd)
        gpus = json.loads(output)
        if isinstance(gpus, dict):
            return [gpus["Name"]]
        return [gpu["Name"] for gpu in gpus]
    except:
        return ["Unknown"]

def get_system_info():
    manufacturer, model = get_manufacturer_and_model()

    return {
        "hostname": get_hostname(),
        "serial_number": get_serial_number(),
        "manufacturer": manufacturer,
        "model": model,
        "os": platform.platform(),
        "ssd_status": detect_ssd(),
        "total_ram_gb": get_total_ram(),
        "cpu_info": get_cpu_info(),
        "gpu_info": get_gpu_info(),
    }
