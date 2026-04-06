FROM ubuntu:latest

WORKDIR /app

# Install Python + venv support (needed to avoid PEP 668 system-pip restriction)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv python3-pip python3-full \
  && rm -rf /var/lib/apt/lists/*

# Create a virtual environment and make it the default python/pip
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies first (better layer caching with docker compose)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir -r /app/requirements.txt