# Frigate SMTP Notifications
Sends email notifications when Frigate NVR detects an object.

`pip install paho-mqtt smtplib requests`

## Setup
This guide assumes you have Home Assistant and Frigate already set up. If you don't, you can follow this tutorial: https://www.youtube.com/watch?v=XWNquH3tNxc (not my video).
This guide also assumes you have access to your Home Assistant integration from outside your local network.

### Setup Gmail SMTP server:
1. Go to https://myaccount.google.com/apppasswords
2. Create a new password with a memorable name like "python" or "smtp"
3. Copy and paste your password into config.json - `"password": "app password goes here",`
4. Change `your-email@gmail.com` in config.json to your email.

### Snapshots:
Modify config.json:
   `"frigate_url": "https://your.homeassistantdomain.com",`

### Setup MQTT:
Modify config.json:
  Change the IP, username, and password to match the user you have made for Home Assistant (or you can make a separate user for this script)

### Configure the script to run on startup (DEBIAN/LINUX ONLY)
1. Install tmux

3. Create a script that starts the tmux session and runs python:

/home/user/startup.sh:
```
#!/bin/bash

# Start a new tmux session named 'emails'
tmux new-session -d -s emails

# Send commands to the 'emails' session
tmux send-keys -t emails 'cd /opt/Frigate-SMTP' C-m
tmux send-keys -t emails 'python3 main.py' C-m
```

sudo chmod +x /home/user/startup.sh

3. Create a systemctl service:

/etc/systemd/system/frigate-smtp.service:
```
[Unit]
Description=Frigate SMTP Service
After=network.target

[Service]
Type=forking
ExecStart=/opt/Frigate-SMTP/startup.sh
WorkingDirectory=/opt/Frigate-SMTP
Restart=on-failure
User=root

[Install]
WantedBy=multi-user.target
```

`sudo systemctl daemon-reload
sudo systemctl enable frigate-smtp.service
sudo systemctl start frigate-smtp.service`

4. Verify it works:

`sudo systemctl status frigate-smtp.service`
OR
`tmux attach -t emails` (remember to exit safely by pressing CTRL+B then D)
