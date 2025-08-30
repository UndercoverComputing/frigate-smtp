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
HOMEASSISTANT_IP = config.get("homeassistant_ip", HOMEASSISTANT_URL)

MQTT_BROKER_IP = config["mqtt"]["broker_ip"]
MQTT_PORT = config["mqtt"]["port"]
MQTT_USERNAME = config["mqtt"]["username"]
MQTT_PASSWORD = config["mqtt"]["password"]

# Load alert rules
try:
    with open("alert_rules.json", "r") as f:
        alert_rules_raw = json.load(f)
    logger.info(f"Loaded alert_rules.json: {alert_rules_raw}")
except Exception as e:
    logger.error(f"Failed to load alert_rules.json, no events will be processed: {e}")
    alert_rules_raw = {}

alert_rules = {}
for cam, rules in alert_rules_raw.items():
    alert_rules[cam.lower()] = {
        "labels": [lbl.lower() for lbl in rules.get("labels", [])],
        "ignore": [lbl.lower() for lbl in rules.get("ignore", [])],
        "zones": [zone.lower() for zone in rules.get("zones", [])]
    }

event_cache = {}


def rule_allows_event(camera, label, zones):
    cam_key = camera.lower()
    lbl = label.lower()
    zones_check = [z.lower() for z in zones] if zones else []

    if cam_key not in alert_rules:
        return False

    rule = alert_rules[cam_key]

    if rule["labels"] and lbl not in rule["labels"]:
        return False
    if rule["ignore"] and lbl in rule["ignore"]:
        return False
    if rule["zones"]:
        if not zones_check:
            return False
        allowed_zones = [z.lower() for z in rule["zones"]]
        if not any(zone in allowed_zones for zone in zones_check):
            return False

    return True


def fetch_snapshot_with_retry(snapshot_url, retries=5, delay=1):
    """
    Try to fetch a valid snapshot, retrying if it fails.
    """
    for attempt in range(retries):
        try:
            response = requests.get(snapshot_url, timeout=5)
            response.raise_for_status()
            if 'image' in response.headers.get('Content-Type', ''):
                return response.content
        except Exception as e:
            logger.debug(f"Snapshot fetch failed (attempt {attempt+1}/{retries}): {e}")
        time.sleep(delay)
    return None


def send_email(message, snapshot_urls, event_label, clip_url):
    subject = f"{event_label} detected!"
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = EMAIL_FROM
    msg['To'] = ", ".join(EMAIL_TO)

    body = f"{message}\n\nClip: {clip_url}"
    msg.attach(MIMEText(body))

    for snapshot_url in snapshot_urls:
        image_bytes = fetch_snapshot_with_retry(snapshot_url)
        if image_bytes:
            msg.attach(MIMEImage(image_bytes, name="snapshot.jpg"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        logger.info(f"Email sent: {subject} to {', '.join(EMAIL_TO)}")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")


def handle_event(event_id):
    if event_id not in event_cache:
        return

    event_info = event_cache[event_id]

    # Don’t send again if already emailed
    if event_info.get("emailed"):
        logger.debug(f"Skipping already emailed event: {event_id}")
        return

    clip_url = f"{HOMEASSISTANT_URL}/api/frigate/notifications/{event_id}/{event_info['camera']}/clip.mp4"
    message = f"A {event_info['event_label']} was detected on camera: {event_info['camera']}.\nEvent ID: {event_id}"

    send_email(message, event_info['snapshot_urls'], event_info['event_label'], clip_url)

    event_cache[event_id]['emailed'] = True
    logger.info(f"Processed and emailed event: {event_id}")


def on_message(client, userdata, message):
    try:
        event_data = json.loads(message.payload.decode("utf-8"))
        if event_data.get("type") != "new":
            return

        after = event_data.get("after")
        if not after:
            return

        event_label = after.get("label")
        event_id = after.get("id")
        camera = after.get("camera")
        zones = after.get("current_zones") or after.get("entered_zones") or []

        if not event_label or not event_id or not camera:
            return

        if not rule_allows_event(camera, event_label, zones):
            logger.info(f"Event from camera '{camera}' with label '{event_label}' and zones '{zones}' blocked by alert rules.")
            return

        snapshot_url = f"{HOMEASSISTANT_IP}/api/frigate/notifications/{event_id}/snapshot.jpg"

        if event_id not in event_cache:
            # First time seeing this event
            event_cache[event_id] = {
                'event_label': event_label,
                'camera': camera,
                'snapshot_urls': [snapshot_url],
                'emailed': False
            }
            # Send email immediately in a thread
            threading.Thread(target=handle_event, args=(event_id,), daemon=True).start()
        else:
            # Already seen this event → just collect snapshots
            event_cache[event_id]['snapshot_urls'].append(snapshot_url)

        logger.info(f"Received event: {event_label} from {camera} (Event ID: {event_id}, Zones: {zones})")

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
