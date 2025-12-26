# =============================================================================
# Vigila.io Local Agent - Dockerfile
# =============================================================================

FROM python:3.11-slim

WORKDIR /app

# Install FFmpeg and other dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Environment variables (override these when running)
ENV VIGILA_TOKEN=""
ENV VIGILA_SERVER_URL=""
ENV AGENT_NAME="local-agent"
ENV HEARTBEAT_INTERVAL=30
ENV LOG_LEVEL=INFO

# Run the agent
CMD ["python", "agent.py"]
