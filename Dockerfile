# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (optional but helps with SSL and DNS)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy files
COPY requirements.txt .
COPY main.py .

# Create a virtual environment
RUN python3 -m venv venv
# Activate the virtual environment
RUN . venv/bin/activate
# Install pip and wheel
RUN python -m ensurepip --upgrade
RUN pip install --no-cache-dir --upgrade pip wheel
# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Environment variable for security (optional)
ENV BOT_TOKEN="REPLACE_HERE"
ENV NOWPAYMENTS_API_KEY="REPLACE_HERE"


# Run the bot
CMD ["python", "main.py"]
