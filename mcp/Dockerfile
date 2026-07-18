# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Install build dependencies (curl) – used by the compose healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application source code
COPY . .

# Expose the MCP server port (default 9000)
EXPOSE 9000

# Command to run the server
CMD ["python", "server.py"]
