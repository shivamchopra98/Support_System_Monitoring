import imaplib
import email
from config import EMAIL_HOST, EMAIL_USER, EMAIL_PASS

def fetch_emails():
    mail = imaplib.IMAP4_SSL(EMAIL_HOST)
    mail.login(EMAIL_USER, EMAIL_PASS)
    mail.select("inbox")

    _, messages = mail.search(None, "UNSEEN")
    email_ids = messages[0].split()

    for e_id in email_ids:
        _, msg_data = mail.fetch(e_id, "(RFC822)")
        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)
        print("📩 New Ticket:", msg["Subject"])

if __name__ == "__main__":
    fetch_emails()
