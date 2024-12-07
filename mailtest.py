import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import json

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Load settings from config.json
with open('config.json', 'r') as f:
    config = json.load(f)

SMTP_SERVER = config["smtp"]["server"]
SMTP_PORT = config["smtp"]["port"]
SMTP_USERNAME = config["smtp"]["username"]
SMTP_PASSWORD = config["smtp"]["password"]
EMAIL_FROM = config["smtp"]["from"]
EMAIL_TO = config["smtp"]["to"]

# Function to send the email
def send_email():
    try:
        subject = "Test Email"
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = EMAIL_FROM
        msg['To'] = ", ".join(EMAIL_TO)

        # Add text to the email
        text = MIMEText("This is a test email.")
        msg.attach(text)

        # Set up the SMTP server connection and send the email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())

        logging.info(f"Email sent successfully to {', '.join(EMAIL_TO)} with subject: {subject}")
    except Exception as e:
        logging.error(f"Failed to send email: {e}")

if __name__ == "__main__":
    send_email()
