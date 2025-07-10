FROM python:3.11-slim

WORKDIR /app

COPY main.py generate_config.py requirements.txt ./

RUN pip3 install --no-cache-dir -r requirements.txt

ENTRYPOINT ["sh", "-c", "python3 generate_config.py && python3 main.py"]
