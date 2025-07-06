#!/bin/bash

# Linux Setup Script for AutoMoto Job Scraper
# This script sets up the Django application with all necessary dependencies

set -e  # Exit on any error

echo "🚀 Setting up AutoMoto Job Scraper for Linux..."
echo "================================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root. Please run as a regular user."
   exit 1
fi

# Update package lists
print_status "Updating package lists..."
sudo apt-get update

# Install system dependencies
print_status "Installing system dependencies..."
sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    libpq-dev \
    curl \
    git \
    wget \
    unzip

# Check if Python 3.8+ is available
python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
required_version="3.8"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    print_error "Python 3.8 or higher is required. Found: $python_version"
    print_status "Installing Python 3.8+..."
    sudo apt-get install -y python3.9 python3.9-pip python3.9-venv
    PYTHON_CMD="python3.9"
else
    PYTHON_CMD="python3"
    print_success "Python version $python_version is compatible"
fi

# Create virtual environment
print_status "Creating virtual environment..."
$PYTHON_CMD -m venv venv

# Activate virtual environment
print_status "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
print_status "Upgrading pip..."
pip install --upgrade pip

# Install Python dependencies
print_status "Installing Python dependencies..."
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    print_status "Creating .env file with default settings..."
    cat > .env << EOF
# Django Settings
DEBUG=True
SECRET_KEY=your-secret-key-here-change-this-in-production
ALLOWED_HOSTS=localhost,127.0.0.1

# Database Settings (SQLite for development)
DATABASE_URL=sqlite:///db.sqlite3

# Scraping Settings
SCRAPING_DELAY=2
MAX_PAGES_PER_SITE=5
REQUEST_TIMEOUT=30

# Logging
LOG_LEVEL=INFO
EOF
    print_warning "Please update the SECRET_KEY in .env file for production use"
fi

# Run Django migrations
print_status "Running Django migrations..."
python manage.py makemigrations
python manage.py migrate

# Create superuser if it doesn't exist
print_status "Creating superuser (if needed)..."
python manage.py shell -c "
from django.contrib.auth.models import User
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('Superuser created: admin/admin123')
else:
    print('Superuser already exists')
"

# Collect static files
print_status "Collecting static files..."
python manage.py collectstatic --noinput

# Create run script
print_status "Creating run script..."
cat > run.sh << 'EOF'
#!/bin/bash
# Run script for AutoMoto Job Scraper

# Activate virtual environment
source venv/bin/activate

# Run Django development server
python manage.py runserver 0.0.0.0:8000
EOF

chmod +x run.sh

# Create production setup script
print_status "Creating production setup script..."
cat > setup_production.sh << 'EOF'
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
EOF

chmod +x setup_production.sh

# Create test script
print_status "Creating test script..."
cat > test_app.py << 'EOF'
#!/usr/bin/env python3
"""
Test script to verify the application setup
"""

import os
import sys
import django
from django.conf import settings

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'automoto.settings')
django.setup()

def test_setup():
    """Test the application setup"""
    print("🧪 Testing AutoMoto Job Scraper setup...")
    print("=" * 50)
    
    # Test database connection
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        print("✅ Database connection: OK")
    except Exception as e:
        print(f"❌ Database connection: FAILED - {e}")
        return False
    
    # Test models
    try:
        from job_scraper.models import CustomWebsite
        print("✅ Models: OK")
    except Exception as e:
        print(f"❌ Models: FAILED - {e}")
        return False
    
    # Test scraper
    try:
        from job_scraper.enhanced_scrapers import EnhancedJobScraper
        scraper = EnhancedJobScraper()
        print("✅ Scraper: OK")
    except Exception as e:
        print(f"❌ Scraper: FAILED - {e}")
        return False
    
    # Test settings
    try:
        print(f"✅ Django version: {django.get_version()}")
        print(f"✅ Debug mode: {settings.DEBUG}")
        print(f"✅ Database: {settings.DATABASES['default']['ENGINE']}")
    except Exception as e:
        print(f"❌ Settings: FAILED - {e}")
        return False
    
    print("=" * 50)
    print("🎉 All tests passed! Setup is complete.")
    return True

if __name__ == "__main__":
    success = test_setup()
    sys.exit(0 if success else 1)
EOF

chmod +x test_app.py

# Create README for this setup
print_status "Creating setup README..."
cat > SETUP_README.md << 'EOF'
# AutoMoto Job Scraper - Linux Setup

## Quick Start

1. **Run the setup script:**
   ```bash
   chmod +x setup_linux.sh
   ./setup_linux.sh
   ```

2. **Test the setup:**
   ```bash
   python test_app.py
   ```

3. **Run the application:**
   ```bash
   ./run.sh
   ```

4. **Access the application:**
   Open your browser and go to: http://localhost:8000

## Default Credentials

- **Admin username:** admin
- **Admin password:** admin123
- **Admin URL:** http://localhost:8000/admin

## Production Setup

For production deployment, run:
```bash
./setup_production.sh
```

This will:
- Install Gunicorn
- Create a systemd service
- Configure for production use

## Troubleshooting

### Common Issues

1. **Permission denied:**
   ```bash
   chmod +x setup_linux.sh
   ```

2. **Python version issues:**
   The script will automatically install Python 3.9 if needed.

3. **Database errors:**
   ```bash
   python manage.py migrate
   ```

4. **Port already in use:**
   Change the port in run.sh or kill the process using port 8000.

### Logs

- Application logs: Check the console output
- Django logs: Check the console output
- System logs: `journalctl -u automoto` (if using systemd)

## File Structure

```
automoto/
├── setup_linux.sh          # This setup script
├── run.sh                  # Development run script
├── setup_production.sh     # Production setup
├── test_app.py            # Setup verification
├── requirements.txt        # Python dependencies
├── .env                   # Environment variables
└── SETUP_README.md        # This file
```

## Next Steps

1. Update the SECRET_KEY in .env for production
2. Configure your database settings
3. Set up proper logging
4. Configure your web server (nginx/apache) for production
EOF

print_success "Linux setup complete!"
echo ""
echo "🎉 AutoMoto Job Scraper is ready to use!"
echo ""
echo "📋 Next steps:"
echo "1. Test the setup: python test_app.py"
echo "2. Run the app: ./run.sh"
echo "3. Open browser: http://localhost:8000"
echo "4. Admin panel: http://localhost:8000/admin (admin/admin123)"
echo ""
echo "📚 For more information, see SETUP_README.md"
echo "" 