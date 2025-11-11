import os
import re
import openai
from config import OPENAI_API_KEY

openai.api_key = OPENAI_API_KEY  # ✅ Correct way to set the API key

LOG_FILE = "logs/system.log"

# Ensure the logs folder and file exist
os.makedirs("logs", exist_ok=True)
if not os.path.exists(LOG_FILE):
    open(LOG_FILE, "w").close()  # Create an empty log file

def analyze_log_with_ai(log_entry):
    """Uses OpenAI to analyze log entries and provide insights."""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # Use "gpt-4" if available
            messages=[
                {"role": "system", "content": "Analyze this log entry and explain the issue:"},
                {"role": "user", "content": log_entry}
            ],
            max_tokens=100
        )
        return response['choices'][0]['message']['content'].strip()
    except openai.error.OpenAIError as e:
        print(f"Error with OpenAI API: {e}")
        return f"Error: {e}"

def monitor_logs():
    """Reads the log file and analyzes error-related entries."""
    detected_logs = []
    with open(LOG_FILE, "r") as file:
        lines = file.readlines()

    for line in lines:
        if re.search(r"error|failed|critical", line, re.IGNORECASE):
            ai_analysis = analyze_log_with_ai(line.strip())  # AI analyzes the log
            detected_logs.append((line.strip(), ai_analysis))
            print(f"⚠️ Log Issue: {line.strip()}")
            print(f"🧠 AI Analysis: {ai_analysis}\n")

    return detected_logs  # Return analyzed logs

if __name__ == "__main__":
    monitor_logs()
