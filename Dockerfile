# Base image with Python 3.11+
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies for Chrome and SeleniumBase
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    build-essential \
    python3-dev \
    libnss3 \
    libgconf-2-4 \
    libxss1 \
    libasound2 \
    libxtst6 \
    libgtk-3-0 \
    libgbm1 \
    && rm -rf /var/lib/apt/lists/*

# Install Google Chrome for SeleniumBase/undetected-chromedriver
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list' && \
    apt-get update && \
    apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# SeleniumBase needs to install its drivers (Chromedriver)
# We use sbase install chromedriver to ensure it's available in the image
RUN sbase install chromedriver

# Copy project files
COPY . .

# Run collectstatic for production-ready serving (optional but recommended)
# RUN python manage.py collectstatic --noinput

# Exposure
EXPOSE 8000

# Default command (will be overridden by docker-compose)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
