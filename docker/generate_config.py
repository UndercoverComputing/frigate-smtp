import json
import os

config = {
    "smtp": {
        "server": os.getenv("SMTP_SERVER", ""),
        "port": int(os.getenv("SMTP_PORT", 587)),
        "username": os.getenv("SMTP_USERNAME", ""),
        "password": os.getenv("SMTP_PASSWORD", ""),
        "from": os.getenv("EMAIL_FROM", ""),
        "to": os.getenv("EMAIL_TO", "").split(",")
    },
    "homeassistant_url": os.getenv("HOMEASSISTANT_URL", ""),
    "homeassistant_ip": os.getenv("HOMEASSISTANT_IP", ""),
    "mqtt": {
        "broker_ip": os.getenv("MQTT_BROKER_IP", ""),
        "port": int(os.getenv("MQTT_PORT", 1883)),
        "username": os.getenv("MQTT_USERNAME", ""),
        "password": os.getenv("MQTT_PASSWORD", "")
    }
}

rules_path = os.getenv("ALERT_RULES_FILE", "alert_rules.json")
if os.path.exists(rules_path):
    with open(rules_path, "r") as f:
        config["alert_rules"] = json.load(f)

with open("config.json", "w") as f:
    json.dump(config, f, indent=2)