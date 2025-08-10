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

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("frigate_event_notifier.log"),
        logging.StreamHandler()
    ]
)

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

try:
    with open("alert_rules.json", "r") as f:
        alert_rules_raw = json.load(f)
    logging.info(f"Loaded alert_rules.json: {alert_rules_raw}")
except Exception as e:
    logging.error(f"Failed to load alert_rules.json, no events will be processed: {e}")
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
        logging.debug(f"Camera '{camera}' not in alert_rules.json — event blocked")
        return False

    rule = alert_rules[cam_key]

    if rule["labels"]:
        if lbl not in rule["labels"]:
            logging.debug(f"Label '{label}' not allowed for camera '{camera}' — event blocked")
            return False

    if rule["ignore"]:
        if lbl in rule["ignore"]:
            logging.debug(f"Label '{label}' is ignored for camera '{camera}' — event blocked")
            return False

    if rule["zones"]:
        if not zones_check:
            logging.debug(f"No zone info in event but zones filter present — event blocked")
            return False
        allowed_zones = [z.lower() for z in rule["zones"]]
        if not any(zone in allowed_zones for zone in zones_check):
            logging.debug(f"Zones {zones} not allowed for camera '{camera}' — event blocked")
            return False

    logging.debug(f"Event allowed for camera '{camera}', label '{label}', zones '{zones}'")
    return True

def send_email(message, snapshot_urls, event_label, clip_url):
    try:
        subject = f"(Test) {event_label} detected!"
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = EMAIL_FROM
        msg['To'] = ", ".join(EMAIL_TO)

        body = f"{message}\n\nClip: {clip_url}"
        msg.attach(MIMEText(body))

        for snapshot_url in snapshot_urls:
            try:
                logging.debug(f"Fetching snapshot: {snapshot_url}")
                response = requests.get(snapshot_url, timeout=5)
                response.raise_for_status()
                image_data = BytesIO(response.content)
                msg.attach(MIMEImage(image_data.read(), name="snapshot.jpg"))
            except Exception as e:
                logging.warning(f"Failed to fetch or attach snapshot {snapshot_url}: {e}")

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())

        logging.info(f"Email sent successfully to {', '.join(EMAIL_TO)} with subject: {subject}")
    except Exception as e:
        logging.error(f"Failed to send email: {e}")

def handle_event(event_id):
    logging.debug(f"Event handler started for event ID: {event_id}")
    time.sleep(7.5)  # Delay to allow snapshots to accumulate

    event_info = event_cache.get(event_id)
    if not event_info:
        logging.warning(f"No cached info found for event ID: {event_id} on handle_event")
        return

    clip_url = f"{HOMEASSISTANT_URL}/api/frigate/notifications/{event_id}/{event_info['camera']}/clip.mp4"
    email_message = f"A {event_info['event_label']} was detected on camera {event_info['camera']}.\nEvent ID: {event_id}"

    send_email(email_message, event_info['snapshot_urls'], event_info['event_label'], clip_url)

    event_cache.pop(event_id, None)
    logging.debug(f"Event ID {event_id} processed and removed from cache")

def on_message(client, userdata, message):
    try:
        event_data = json.loads(message.payload.decode("utf-8"))
        logging.debug(f"Received MQTT message: {event_data}")

        if event_data.get("type") != "new":
            logging.debug("Event type is not 'new', ignoring.")
            return

        after = event_data.get("after")
        if not after:
            logging.debug("No 'after' data in event, ignoring.")
            return

        event_label = after.get("label")
        event_id = after.get("id")
        camera = after.get("camera")
        # Use correct zone info as list
        zones = after.get("current_zones") or after.get("entered_zones") or []

        if not event_label or not event_id or not camera:
            logging.debug("Missing label, id or camera in event, ignoring.")
            return

        if not rule_allows_event(camera, event_label, zones):
            logging.info(f"Event from camera '{camera}' with label '{event_label}' and zones '{zones}' blocked by alert rules.")
            return

        snapshot_url = f"{HOMEASSISTANT_IP}/api/frigate/notifications/{event_id}/snapshot.jpg"

        if event_id in event_cache:
            event_cache[event_id]['snapshot_urls'].append(snapshot_url)
            logging.debug(f"Added snapshot to existing event cache: {event_id}")
        else:
            event_cache[event_id] = {
                'event_label': event_label,
                'camera': camera,
                'snapshot_urls': [snapshot_url],
                'timer': threading.Thread(target=handle_event, args=(event_id,))
            }
            event_cache[event_id]['timer'].start()
            logging.debug(f"Started new event handler thread for event ID: {event_id}")

        logging.info(f"Event processed: {event_label} - Event ID: {event_id} from camera: {camera} Zones: {zones}")

    except Exception as e:
        logging.error(f"Error processing MQTT message: {e}")

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logging.info("Connected to MQTT broker successfully")
        client.subscribe("frigate/events")
    else:
        logging.error(f"Failed to connect to MQTT broker. Return code: {rc}")

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
    print("WARNING: USE THIS FOR TESTING AND DEBUGGING ONLY!")
    logging.warning("WARNING: USE THIS FOR TESTING AND DEBUGGING ONLY!")
    time.sleep(2)
    print("WARNING: USE THIS FOR TESTING AND DEBUGGING ONLY!")
    logging.warning("WARNING: USE THIS FOR TESTING AND DEBUGGING ONLY!")

    logging.info("Starting Frigate Event Notifier...")
    connect_mqtt()