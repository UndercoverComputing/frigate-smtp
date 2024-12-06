# Import necessary dependencies
import paho.mqtt.client as mqtt
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import requests
import json
from io import BytesIO
import time
import threading

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
    subject = f"Object Detected: {event_label}"
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = EMAIL_FROM
    msg['To'] = ", ".join(EMAIL_TO)

    # Add the email body
    body = f"{message}\n\nAn object was detected at the Gate!\n\nClip link: {clip_url}"
    msg.attach(MIMEText(body))

    # Attach snapshots to the email
    for snapshot_url in snapshot_urls:
        response = requests.get(snapshot_url)
        image_data = BytesIO(response.content)
        msg.attach(MIMEImage(image_data.read(), name="snapshot.jpg"))

    # Send the email
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())

    # Print the status of the email
    print(f"Email sent to {', '.join(EMAIL_TO)} with subject: {subject}")

# Function to handle the event timeout and send email after waiting for new snapshots
def handle_event(event_id, event_label, snapshot_urls):
    time.sleep(10)  # Wait for more snapshots before sending email

    clip_url = f"{FRIGATE_URL}/api/frigate/notifications/{event_id}/gate/clip.mp4"
    email_message = f"A {event_label} was detected.\nEvent ID: {event_id}"
    send_email(email_message, snapshot_urls, event_label, clip_url)

    # Print message after email is sent
    print(f"Sent email for event: {event_label} (Event ID: {event_id})")

    # Remove event from cache after processing
    event_cache.pop(event_id, None)

# MQTT message callback
def on_message(client, userdata, message):
    try:
        event_data = json.loads(message.payload.decode("utf-8"))
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

        # Print when motion is detected
        print(f"Motion detected: {event_label} (Event ID: {event_id})")

    except Exception as e:
        pass  # Ignore errors in message processing

# MQTT connection callback
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        client.subscribe("frigate/events")

# MQTT setup
def connect_mqtt():
    client = mqtt.Client()
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(MQTT_BROKER_IP, MQTT_PORT, 60)
        client.loop_forever()
    except Exception as e:
        pass  # Ignore connection errors

if __name__ == "__main__":
    connect_mqtt()
