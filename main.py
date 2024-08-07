import imaplib
import email
from email.header import decode_header
from twilio.rest import Client
import re
from datetime import datetime
from dateutil import parser
import os

# Email credentials
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASS = os.getenv('EMAIL_PASS')
EMAIL_SERVER = 'imap.gmail.com'

# Twilio credentials
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
YOUR_PHONE_NUMBER = os.getenv('YOUR_PHONE_NUMBER')

# Login to email
def login_to_email():
    mail = imaplib.IMAP4_SSL(EMAIL_SERVER)
    mail.login(EMAIL_USER, EMAIL_PASS)
    return mail

# Search for unread emails from a specific sender
def search_unread_emails(mail, folder, sender):
    mail.select(folder)
    status, messages = mail.search(None, f'(UNSEEN FROM "{sender}")')
    email_ids = messages[0].split()
    return email_ids

# Extract email details
def extract_email_details(mail, email_id):
    status, msg_data = mail.fetch(email_id, "(RFC822)")
    raw_email = msg_data[0][1]
    msg = email.message_from_bytes(raw_email)

    # Get email subject
    subject, encoding = decode_header(msg["Subject"])[0]
    if isinstance(subject, bytes):
        subject = subject.decode(encoding if encoding else "utf-8")

    # Extract email body
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            if content_type == "text/plain" and "attachment" not in content_disposition:
                body = part.get_payload(decode=True).decode()
                break
            elif content_type == "text/html" and "attachment" not in content_disposition:
                body = part.get_payload(decode=True).decode()
                break
    else:
        body = msg.get_payload(decode=True).decode()

    return subject, body

def parse_email_details(body):
    # Adjust the regular expressions to account for the asterisks around the labels
    company_name = re.search(r'\*Company\s*:\s*\*(.+)', body)
    ctc = re.search(r'\*Expected CTC\s*:\s*\*([\d.,\-]+)', body)
    deadline = re.search(r'\*Last date to Apply\s*:\s*\*(.+)', body)

    company_name = company_name.group(1).strip() if company_name else "N/A"
    ctc = ctc.group(1).strip() if ctc else "N/A"
    deadline = deadline.group(1).strip() if deadline else "N/A"

    # Parse the deadline to a proper datetime format
    try:
        deadline_date = parser.parse(deadline)
        deadline = deadline_date.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        deadline = "N/A"

    return company_name, ctc, deadline

# Make a phone call using Twilio
def make_call(company_name, ctc, deadline):
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    call = client.calls.create(
        twiml=f'<Response><Say>Hello! You have received a new email from {company_name}. The CTC is {ctc}. Please note the deadline to register is {deadline}. Thank you!</Say></Response>',
        to=YOUR_PHONE_NUMBER,
        from_=TWILIO_PHONE_NUMBER
    )
    print(f"Call initiated: {call.sid}")

# Main function
def process_emails():
    mail = login_to_email()

    # Check inbox for unread emails
    email_ids = search_unread_emails(mail, 'inbox', 'mail@gmail.com')

    # Check spam for unread emails if not found in inbox
    if not email_ids:
        email_ids = search_unread_emails(mail, '[Gmail]/Spam', 'mail@gmail.com')

    if email_ids:
        for email_id in email_ids:
            subject, body = extract_email_details(mail, email_id)
            print(f"Found Unread Email - Subject: {subject}")
            print(f"Body: {body}")

            company_name, ctc, deadline = parse_email_details(body)
            print(f"Extracted Details - Company: {company_name}, CTC: {ctc}, Deadline: {deadline}")

            make_call(company_name, ctc, deadline)

            # Mark the email as read after processing
            mail.store(email_id, '+FLAGS', '\\Seen')
            
            break
    else:
        print("No unread emails found from the specified sender.")

    mail.logout()

process_emails()


