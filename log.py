# Import necessary dependencies.
import paho.mqtt.client as mqtt
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import requests
import json
import logging
from io import BytesIO
import time
import threading

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("frigate_event_notifier.log"),
        logging.StreamHandler()
    ]
)

# Load settings from config.json
with open('config.json', 'r') as f:
    config = json.load(f)

SMTP_SERVER = config["smtp"]["server"]
SMTP_PORT = config["smtp"]["port"]
SMTP_USERNAME = config["smtp"]["username"]
SMTP_PASSWORD = config["smtp"]["password"]
EMAIL_FROM = config["smtp"]["from"]
EMAIL_TO = config["smtp"]["to"]
FRIGATE_URL = config["frigate_url"]

# MQTT configuration
MQTT_BROKER_IP = config["mqtt"]["broker_ip"]
MQTT_PORT = config["mqtt"]["port"]
MQTT_USERNAME = config["mqtt"]["username"]
MQTT_PASSWORD = config["mqtt"]["password"]

# Dictionary to track event IDs and email state
event_cache = {}

# Function to send email with attachment and clip link
def send_email(message, snapshot_urls, event_label, clip_url):
    try:
        subject = f"(Test) {event_label} detected!"
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = EMAIL_FROM
        msg['To'] = ", ".join(EMAIL_TO)

        # Add the email body
        body = f"{message}\n\nClip: {clip_url}"
        msg.attach(MIMEText(body))

        # Attach snapshots to the email
        for snapshot_url in snapshot_urls:
            response = requests.get(snapshot_url)
            response.raise_for_status()
            image_data = BytesIO(response.content)
            msg.attach(MIMEImage(image_data.read(), name="snapshot.jpg"))

        # Send the email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())

        logging.info(f"Email sent successfully to {', '.join(EMAIL_TO)} with subject: {subject}")
    except Exception as e:
        logging.error(f"Failed to send email: {e}")

# Function to handle the event timeout and send email after waiting for new snapshots
def handle_event(event_id, event_label, snapshot_urls):
    time.sleep(7.5)  # Wait for more snapshots before sending email

    clip_url = f"{FRIGATE_URL}/api/frigate/notifications/{event_id}/gate/clip.mp4"
    email_message = f"A {event_label} was detected.\nEvent ID: {event_id}"
    send_email(email_message, snapshot_urls, event_label, clip_url)

    # Remove event from cache after processing
    event_cache.pop(event_id, None)

# MQTT message callback
def on_message(client, userdata, message):
    try:
        event_data = json.loads(message.payload.decode("utf-8"))
        logging.debug(f"Frigate event data: {event_data}")

        event_label = event_data["after"]["label"]
        event_id = event_data["after"]["id"]
        snapshot_url = f"{FRIGATE_URL}/api/frigate/notifications/{event_id}/snapshot.jpg"

        if event_id in event_cache:
            event_cache[event_id]['snapshot_urls'].append(snapshot_url)
        else:
            event_cache[event_id] = {
                'event_label': event_label,
                'snapshot_urls': [snapshot_url],
                'timer': threading.Thread(target=handle_event, args=(event_id, event_label, [snapshot_url]))
            }
            event_cache[event_id]['timer'].start()

        logging.info(f"Event processed: {event_label} - Event ID: {event_id}")
    except Exception as e:
        logging.error(f"Error processing MQTT message: {e}")

# MQTT connection callback
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logging.info("Connected to MQTT broker successfully")
        client.subscribe("frigate/events")
    else:
        logging.error(f"Failed to connect to MQTT broker. Return code: {rc}")

# MQTT setup
def connect_mqtt():
    client = mqtt.Client()
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        logging.info("Attempting to connect to MQTT broker...")
        client.connect(MQTT_BROKER_IP, MQTT_PORT, 60)
        client.loop_forever()
    except Exception as e:
        logging.error(f"Error during MQTT connection: {e}")

if __name__ == "__main__":
    # Print or log the warning message when the script is run
    print("WARNING: USE THIS FOR TESTING AND DEBUGGING ONLY!")
    logging.warning("WARNING: USE THIS FOR TESTING AND DEBUGGING ONLY!")
    time.sleep(2)
    print("WARNING: USE THIS FOR TESTING AND DEBUGGING ONLY!")
    logging.warning("WARNING: USE THIS FOR TESTING AND DEBUGGING ONLY!")
    
    logging.info("Starting Frigate Event Notifier...")
    connect_mqtt()
