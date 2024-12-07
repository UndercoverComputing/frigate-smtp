# Frigate SMTP Notifications
Sends email notifications when Frigate NVR detects an object.

## Setup
This guide assumes you have Home Assistant and Frigate already set up. If you don't, you can follow this tutorial: https://www.youtube.com/watch?v=XWNquH3tNxc (not my video).
This guide also assumes you have access to your Home Assistant integration from outside your local network.

### Setup Gmail SMTP server:
1. Go to https://myaccount.google.com/apppasswords
2. Create a new password with a memorable name like "python" or "smtp"
3. Copy and paste your password into config.json - `"password": "app password goes here",`
4. Change your-email@gmail.com to your email.

### Snapshots:
Modify config.json:
   `"frigate_url": "https://your.homeassistantdomain.com",`

### Setup MQTT:
Modify config.json:
  Change the IP, username, and password to match the user you have made for Home Assistant (or you can make a separate user for this script)
