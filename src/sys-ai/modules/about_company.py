import streamlit as st
import PyPDF2
import openai
import os
import re



def read_pdf(file_path):
    """Extract text from PDF file."""
    with open(file_path, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
    return text

def highlight_entities(text):
    """Highlight names, locations, and mask sensitive info."""
    # Example patterns (adjust based on company data)
    name_pattern = r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\b"  # Detect names like "John Doe"
    location_pattern = r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\b"  # Detect locations
    gst_pattern = r"\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}\d{1}[Z]{1}[A-Z\d]{1}\b"  # GST Number
    account_pattern = r"\b\d{9,18}\b"  # Bank account numbers (9-18 digits)

    # Highlight Names & Locations
    text = re.sub(name_pattern, r'**🟢 \1**', text)
    text = re.sub(location_pattern, r'**📍 \1**', text)

    # Mask Sensitive Information
    text = re.sub(gst_pattern, "[🔒 GST Number Hidden]", text)
    text = re.sub(account_pattern, "[🔒 Account Number Hidden]", text)

    return text

def summarize_company_info(text):
    """Use AI to generate a summary of the company information."""
    text = highlight_entities(text)
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Summarize the following company details."},
            {"role": "user", "content": text}
        ]
    )
    return response["choices"][0]["message"]["content"]

def answer_company_question(text, question):
    """Use AI to answer specific questions about the company."""
    text = highlight_entities(text)
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Answer the question based on the given company details."},
            {"role": "user", "content": f"Company Info: {text}\nQuestion: {question}"}
        ]
    )
    return response["choices"][0]["message"]["content"]

def about_company_ui():
    """Streamlit UI for displaying company details."""
    st.title("🏢 About Company")
    file_path = "modules/TechNova Solutions.pdf"  # Ensure this file exists in modules folder
    
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
