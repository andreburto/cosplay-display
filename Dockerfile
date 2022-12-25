FROM python:3.9-slim-buster

COPY requirements.txt /tmp/requirements.txt

RUN python3 -m pip install -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt && \
    python3 -m pip cache purge

WORKDIR /app

CMD ["python3", "cosplay-display.py"]
