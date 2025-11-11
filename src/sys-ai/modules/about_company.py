import streamlit as st
import PyPDF2
import boto3
import json
import os
import re

# Create Bedrock runtime client
bedrock = boto3.client(service_name="bedrock-runtime", region_name="us-east-1")

def read_pdf(file_path):
    """Extract text from PDF file."""
    with open(file_path, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
    return text

def highlight_entities(text):
    """Highlight names, locations, and mask sensitive info."""
    name_pattern = r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\b"
    location_pattern = r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\b"
    gst_pattern = r"\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}\d{1}[Z]{1}[A-Z\d]{1}\b"
    account_pattern = r"\b\d{9,18}\b"

    text = re.sub(name_pattern, r'**🟢 \1**', text)
    text = re.sub(location_pattern, r'**📍 \1**', text)
    text = re.sub(gst_pattern, "[🔒 GST Number Hidden]", text)
    text = re.sub(account_pattern, "[🔒 Account Number Hidden]", text)

    return text

def bedrock_claude_response(prompt):
    """Utility function to get Claude 3 Sonnet response."""
    try:
        model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}]
        })
        response = bedrock.invoke_model(modelId=model_id, body=body)
        result = json.loads(response['body'].read())
        return result["content"][0]["text"]
    except Exception as e:
        return f"Error communicating with AWS Bedrock: {e}"

def summarize_company_info(text):
    text = highlight_entities(text)
    prompt = f"Summarize the following company details clearly and concisely:\n\n{text}"
    return bedrock_claude_response(prompt)

def answer_company_question(text, question):
    text = highlight_entities(text)
    prompt = f"Company Information:\n{text}\n\nQuestion: {question}\nAnswer based only on the provided company details."
    return bedrock_claude_response(prompt)

def about_company_ui():
    st.title("🏢 About Company")
    file_path = "modules/TechNova Solutions.pdf"

    if os.path.exists(file_path):
        if st.button("📄 Start - Learn About the Company", use_container_width=True):
            text = read_pdf(file_path)
            summary = summarize_company_info(text)
            st.write("### 🏢 Company Summary:")
            st.info(summary)

        question = st.text_input("🔍 Ask a question about the company:")
        if st.button("Ask", use_container_width=True):
            if question.strip():
                text = read_pdf(file_path)
                answer = answer_company_question(text, question)
                st.success(answer)
            else:
                st.warning("⚠️ Please enter a valid question.")
    else:
        st.error("❌ Company PDF file not found. Please upload the correct file.")
