# Base image with Python 3.11+
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install bare essentials for downloading and installing further tools
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Install Playwright and let it handle the heavy lifting for Chromium dependencies
# This automatically identifies and installs the correct libraries for your base image
RUN playwright install chromium && \
    playwright install-deps chromium

# Copy project files
COPY . .

# Exposure
EXPOSE 8000

# Default command (will be overridden by docker-compose)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
