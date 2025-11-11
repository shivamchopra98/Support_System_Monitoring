import psutil
import boto3
import json

bedrock = boto3.client(service_name="bedrock-runtime", region_name="us-east-1")

def system_health_prediction():
    ram_usage = psutil.virtual_memory().percent
    cpu_usage = psutil.cpu_percent(interval=1)
    disk_usage = psutil.disk_usage('/').percent

    prompt = (
        f"RAM: {ram_usage}%, CPU: {cpu_usage}%, Disk: {disk_usage}%.\n"
        f"Predict system health: Good, Warning, or Critical — and explain briefly."
    )

    model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 256,
        "messages": [{"role": "user", "content": prompt}]
    })

    try:
        response = bedrock.invoke_model(modelId=model_id, body=body)
        result = json.loads(response['body'].read())
        prediction_text = result["content"][0]["text"]

        if ram_usage < 50 and cpu_usage < 50 and disk_usage < 70:
            status = "Good"
        elif ram_usage < 80 and cpu_usage < 80 and disk_usage < 90:
            status = "Warning"
        else:
            status = "Critical"

        return {
            "ram": ram_usage,
            "cpu": cpu_usage,
            "disk": disk_usage,
            "status": status,
            "prediction": prediction_text
        }
    except Exception as e:
        return {"ram": ram_usage, "cpu": cpu_usage, "disk": disk_usage, "status": "Error", "prediction": str(e)}
