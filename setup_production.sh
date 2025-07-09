#!/bin/bash
# Production setup script

echo "Setting up AutoMoto Job Scraper for production..."

# Install production dependencies
pip install gunicorn

# Create gunicorn configuration
cat > gunicorn.conf.py << 'GUNICORN_EOF'
bind = "0.0.0.0:8000"
workers = 3
timeout = 120
max_requests = 1000
max_requests_jitter = 100
preload_app = True
GUNICORN_EOF

# Create systemd service file
sudo tee /etc/systemd/system/automoto.service > /dev/null << 'SERVICE_EOF'
[Unit]
Description=AutoMoto Job Scraper
After=network.target

[Service]
Type=notify
User=$USER
WorkingDirectory=$(pwd)
Environment=PATH=$(pwd)/venv/bin
ExecStart=$(pwd)/venv/bin/gunicorn --config gunicorn.conf.py automoto.wsgi:application
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE_EOF

echo "Production setup complete!"
echo "To start the service: sudo systemctl start automoto"
echo "To enable on boot: sudo systemctl enable automoto"
