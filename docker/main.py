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
import logging

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Load config
with open('config.json', 'r') as f:
    config = json.load(f)

SMTP_SERVER = config["smtp"]["server"]
SMTP_PORT = config["smtp"]["port"]
SMTP_USERNAME = config["smtp"]["username"]
SMTP_PASSWORD = config["smtp"]["password"]
EMAIL_FROM = config["smtp"]["from"]
EMAIL_TO = config["smtp"]["to"]
HOMEASSISTANT_URL = config["homeassistant_url"]
HOMEASSISTANT_IP = config["homeassistant_ip"]

MQTT_BROKER_IP = config["mqtt"]["broker_ip"]
MQTT_PORT = config["mqtt"]["port"]
MQTT_USERNAME = config["mqtt"]["username"]
MQTT_PASSWORD = config["mqtt"]["password"]

FILTERED_CAMERAS = config.get("allowed_cameras", [])
IGNORED_LABELS = config.get("ignored_labels", [])

event_cache = {}

def send_email(message, snapshot_urls, event_label, clip_url):
    subject = f"{event_label} detected!"
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = EMAIL_FROM
    msg['To'] = ", ".join(EMAIL_TO)

    body = f"{message}\n\nClip: {clip_url}"
    msg.attach(MIMEText(body))

    for snapshot_url in snapshot_urls:
        try:
            response = requests.get(snapshot_url, timeout=5)
            response.raise_for_status()
            if 'image' in response.headers.get('Content-Type', ''):
                image_data = BytesIO(response.content)
                msg.attach(MIMEImage(image_data.read(), name="snapshot.jpg"))
        except Exception:
            pass  # silent fail for snapshot issues

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        logger.info(f"Email sent: {subject} to {', '.join(EMAIL_TO)}")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")

def handle_event(event_id):
    time.sleep(10)  # Delay to collect full snapshots

    if event_id not in event_cache:
        return

    event_info = event_cache[event_id]
    clip_url = f"{HOMEASSISTANT_URL}/api/frigate/notifications/{event_id}/{event_info['camera']}/clip.mp4"
    message = f"A {event_info['event_label']} was detected on camera: {event_info['camera']}.\nEvent ID: {event_id}"
    send_email(message, event_info['snapshot_urls'], event_info['event_label'], clip_url)

    logger.info(f"Processed and emailed event: {event_id}")
    event_cache.pop(event_id, None)

def on_message(client, userdata, message):
    try:
        event_data = json.loads(message.payload.decode("utf-8"))
        if event_data.get("type") != "new":
            return

        after = event_data.get("after")
        if not after:
            return

        event_id = after.get("id")
        event_label = after.get("label")
        camera = after.get("camera")

        if not event_id or not event_label or not camera:
            return

        if FILTERED_CAMERAS and camera.lower() not in [c.lower() for c in FILTERED_CAMERAS]:
            return

        if event_label in IGNORED_LABELS:
            return

        snapshot_url = f"{HOMEASSISTANT_IP}/api/frigate/notifications/{event_id}/snapshot.jpg"

        if event_id in event_cache:
            event_cache[event_id]['snapshot_urls'].append(snapshot_url)
        else:
            event_cache[event_id] = {
                'event_label': event_label,
                'camera': camera,
                'snapshot_urls': [snapshot_url]
            }
            threading.Thread(target=handle_event, args=(event_id,), daemon=True).start()

        logger.info(f"Received event: {event_label} from {camera} (Event ID: {event_id})")

    except Exception as e:
        logger.error(f"Error processing MQTT message: {e}")

def on_connect(client, userdata, flags, rc, properties=None):
    if rc != 0:
        logger.error(f"MQTT connection failed with code {rc}")
        return

    if userdata.get("first_connect", True):
        client.subscribe("frigate/events")
        logger.info("Connected to MQTT broker and subscribed to frigate/events")
        userdata["first_connect"] = False
    else:
        logger.debug("Reconnected to MQTT broker")

def connect_mqtt():
    client = mqtt.Client(
        client_id="frigate_smtp",
        protocol=mqtt.MQTTv5,
        userdata={"first_connect": True}
    )
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message

    while True:
        try:
            logger.info("Connecting to MQTT broker...")
            client.connect(MQTT_BROKER_IP, MQTT_PORT, 60)
            client.loop_start()
            while True:
                time.sleep(1)
        except Exception as e:
            logger.error(f"MQTT connection failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)

if __name__ == "__main__":
    connect_mqtt()
