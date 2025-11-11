import boto3
import json

# Create Bedrock client
bedrock = boto3.client(service_name="bedrock-runtime", region_name="us-east-1")

def get_chatbot_response(user_query):
    try:
        model_id = "anthropic.claude-3-sonnet-20240229-v1:0"

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 512,
            "messages": [
                {"role": "user", "content": user_query}
            ]
        })

        response = bedrock.invoke_model(modelId=model_id, body=body)
        result = json.loads(response['body'].read())
        return result["content"][0]["text"]

    except Exception as e:
        print(f"Error communicating with AWS Bedrock: {e}")
        return f"Error: {e}"
