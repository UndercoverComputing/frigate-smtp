# Frigate SMTP

This repository provides an SMTP service for Frigate, enabling automated email notifications for detected events. Each alert includes an attached snapshot of the event and a URL linking to the corresponding video clip. Example email:
![image](https://github.com/user-attachments/assets/17504338-d941-4114-a78a-d50350b7bedc)
~# Some information redacted for privacy.

## Prerequisites

- [Docker](https://www.docker.com/get-started) installed on your system
- [Docker Compose](https://docs.docker.com/compose/install/) installed
- Git installed to clone the repository

## Project Structure

```
/docker
├── main.py              # Main application script
├── generate_config.py   # Script to generate configuration
├── Dockerfile           # Docker image definition
├── docker-compose.yaml  # Docker Compose configuration
└── requirements.txt     # Python dependencies
```

## Installation and Usage

Follow these steps to set up and run the Frigate SMTP service:

1. **Clone the Repository**

   ```bash
   git clone https://github.com/The-Dark-Mode/frigate-smtp
   cd frigate-smtp/docker/
   ```

2. **Configure Environment Variables**

   Open the `docker-compose.yaml` file in a text editor and define the necessary environment variables. Ensure all required variables (e.g., SMTP server settings) are correctly set.

   Example snippet from `docker-compose.yaml`:
   ```yaml
    services:
      frigate-smtp:
        build: .    # Build image from local Dockerfile in current directory
        container_name: frigate-smtp    # Set container name for easier management
        image: frigate-smtp    # Name of the Docker image
        restart: unless-stopped    # Automatically restart container unless manually stopped
        environment:    # Environment variables to configure the service
          SMTP_SERVER: smtp.example.com    # SMTP server address for sending emails
          SMTP_PORT: 587    # SMTP server port (usually 587 for TLS)
          SMTP_USERNAME: user@example.com    # SMTP username for authentication
          SMTP_PASSWORD: yourpassword    # SMTP password for authentication
          EMAIL_FROM: user@example.com    # Sender email address
          EMAIL_TO: you@example.com,friend@example.com     # Recipient email addresses (comma-separated)
          HOMEASSISTANT_URL: https://ha.domain.com    # URL to Home Assistant instance (external)
          HOMEASSISTANT_IP: http://ha-ip:8123    # Home Assistant internal IP URL
          MQTT_BROKER_IP: mqtt-ip    # MQTT broker IP address
          MQTT_PORT: 1883    # MQTT broker port
          MQTT_USERNAME: mqttuser    # MQTT username for authentication
          MQTT_PASSWORD: mqttpass    # MQTT password for authentication
          ALLOWED_CAMERAS: camera1,camera2    # List of cameras to allow (comma-separated)
          IGNORED_LABELS: label1,label2    # Labels to ignore - e.g. car, person, cat; if none, set to "..."
   ```

   Replace `your.smtp.server`, `587`, `your_username`, and `your_password` with your actual SMTP server details.

3. **Run the Application**

   Build and start the Docker containers in detached mode:

   ```bash
   docker compose up --build -d
   ```

   - The `--build` flag ensures the Docker image is built before starting.
   - The `-d` flag runs the containers in the background.

4. **Verify the Service**

   Check the container logs to ensure the service is running correctly:

   ```bash
   docker compose logs
   ```

## Stopping the Service

To stop the running containers:

```bash
docker compose down
```

## Troubleshooting

- Ensure all environment variables in `docker-compose.yaml` are correctly set.
- Verify that your SMTP server is accessible and the credentials are valid.
- Check Docker logs for errors: `docker compose logs frigate-smtp`.
- Ensure Docker and Docker Compose are up to date.

## Contributing

Contributions are welcome! Please fork the repository, create a new branch, and submit a pull request with your changes.
