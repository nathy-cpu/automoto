@echo off
setlocal enabledelayedexpansion

REM Windows Setup Script for AutoMoto Job Scraper
REM This script sets up the Django application with all necessary dependencies

echo 🚀 Setting up AutoMoto Job Scraper for Windows...
echo ================================================

REM Check if running as administrator
net session >nul 2>&1
if %errorLevel% == 0 (
    echo [ERROR] This script should not be run as administrator. Please run as a regular user.
    pause
    exit /b 1
)

REM Check if Python is installed
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.8+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

REM Check Python version
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [INFO] Found Python version: %PYTHON_VERSION%

REM Check if pip is available
pip --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] pip is not available. Please install pip or reinstall Python.
    pause
    exit /b 1
)

REM Create virtual environment
echo [INFO] Creating virtual environment...
python -m venv venv
if %errorLevel% neq 0 (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
)

REM Activate virtual environment
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat
if %errorLevel% neq 0 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)

REM Upgrade pip
echo [INFO] Upgrading pip...
python -m pip install --upgrade pip

REM Install Python dependencies
echo [INFO] Installing Python dependencies...
pip install -r requirements.txt

REM Install development dependencies (optional)
echo [INFO] Installing development dependencies...
pip install -r requirements-dev.txt
if %errorLevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

REM Create .env file if it doesn't exist
if not exist .env (
    echo [INFO] Creating .env file with default settings...
    (
        echo # Django Settings
        echo DEBUG=True
        echo SECRET_KEY=your-secret-key-here-change-this-in-production
        echo ALLOWED_HOSTS=localhost,127.0.0.1
        echo.
        echo # Database Settings ^(SQLite for development^)
        echo DATABASE_URL=sqlite:///db.sqlite3
        echo.
        echo # Scraping Settings
        echo SCRAPING_DELAY=2
        echo MAX_PAGES_PER_SITE=5
        echo REQUEST_TIMEOUT=30
        echo.
        echo # Logging
        echo LOG_LEVEL=INFO
    ) > .env
    echo [WARNING] Please update the SECRET_KEY in .env file for production use
)

REM Run Django migrations
echo [INFO] Running Django migrations...
python manage.py makemigrations
python manage.py migrate

REM Create superuser if it doesn't exist
echo [INFO] Creating superuser ^(if needed^)...
python manage.py shell -c "from django.contrib.auth.models import User; User.objects.get_or_create(username='admin', defaults={'is_superuser': True, 'is_staff': True, 'email': 'admin@example.com'})[0].set_password('admin123') and None or print('Superuser created: admin/admin123')"

REM Collect static files (skip if no static files exist)
echo [INFO] Collecting static files...
if exist static\ (
    python manage.py collectstatic --noinput
) else if exist job_scraper\static\ (
    python manage.py collectstatic --noinput
) else (
    echo [INFO] No static files found, skipping collectstatic
)

REM Create run script
echo [INFO] Creating run script...
(
    echo @echo off
    echo REM Run script for AutoMoto Job Scraper
    echo.
    echo REM Activate virtual environment
    echo call venv\Scripts\activate.bat
    echo.
    echo REM Run Django development server
    echo python manage.py runserver 0.0.0.0:8000
    echo pause
) > run.bat

REM Create test script
echo [INFO] Creating test script...
(
    echo @echo off
    echo REM Test script to verify the application setup
    echo.
    echo call venv\Scripts\activate.bat
    echo python test_app.py
    echo pause
) > test_app.bat

REM Create the Python test script
(
    echo #!/usr/bin/env python3
    echo """
    echo Test script to verify the application setup
    echo """
    echo.
    echo import os
    echo import sys
    echo import django
    echo from django.conf import settings
    echo.
    echo # Add the project directory to Python path
    echo sys.path.append^(os.path.dirname^(os.path.abspath^(__file__^)^)^)
    echo.
    echo # Setup Django
    echo os.environ.setdefault^('DJANGO_SETTINGS_MODULE', 'automoto.settings'^)
    echo django.setup^(^)
    echo.
    echo def test_setup^(^):
    echo     """Test the application setup"""
    echo     print^("🧪 Testing AutoMoto Job Scraper setup..."^)
    echo     print^("=" * 50^)
    echo     
    echo     # Test database connection
    echo     try:
    echo         from django.db import connection
    echo         with connection.cursor^(^) as cursor:
    echo             cursor.execute^("SELECT 1"^)
    echo         print^("✅ Database connection: OK"^)
    echo     except Exception as e:
    echo         print^(f"❌ Database connection: FAILED - {e}"^)
    echo         return False
    echo     
    echo     # Test models
    echo     try:
    echo         from job_scraper.models import CustomWebsite
    echo         print^("✅ Models: OK"^)
    echo     except Exception as e:
    echo         print^(f"❌ Models: FAILED - {e}"^)
    echo         return False
    echo     
    echo     # Test scraper
    echo     try:
    echo         from job_scraper.enhanced_scrapers import EnhancedJobScraper
    echo         scraper = EnhancedJobScraper^(^)
    echo         print^("✅ Scraper: OK"^)
    echo     except Exception as e:
    echo         print^(f"❌ Scraper: FAILED - {e}"^)
    echo         return False
    echo     
    echo     # Test settings
    echo     try:
    echo         print^(f"✅ Django version: {django.get_version^(^)}"^)
    echo         print^(f"✅ Debug mode: {settings.DEBUG}"^)
    echo         print^(f"✅ Database: {settings.DATABASES['default']['ENGINE']}"^)
    echo     except Exception as e:
    echo         print^(f"❌ Settings: FAILED - {e}"^)
    echo         return False
    echo     
    echo     print^("=" * 50^)
    echo     print^("🎉 All tests passed! Setup is complete."^)
    echo     return True
    echo.
    echo if __name__ == "__main__":
    echo     success = test_setup^(^)
    echo     sys.exit^(0 if success else 1^)
) > test_app.py

REM Create README for this setup
echo [INFO] Creating setup README...
(
    echo # AutoMoto Job Scraper - Windows Setup
    echo.
    echo ## Quick Start
    echo.
    echo 1. **Run the setup script:**
    echo    ```cmd
    echo    setup_windows.bat
    echo    ```
    echo.
    echo 2. **Test the setup:**
    echo    ```cmd
    echo    test_app.bat
    echo    ```
    echo.
    echo 3. **Run the application:**
    echo    ```cmd
    echo    run.bat
    echo    ```
    echo.
    echo 4. **Access the application:**
    echo    Open your browser and go to: http://localhost:8000
    echo.
    echo ## Default Credentials
    echo.
    echo - **Admin username:** admin
    echo - **Admin password:** admin123
    echo - **Admin URL:** http://localhost:8000/admin
    echo.
    echo ## Troubleshooting
    echo.
    echo ### Common Issues
    echo.
    echo 1. **Python not found:**
    echo    Install Python 3.8+ from https://www.python.org/downloads/
    echo    Make sure to check "Add Python to PATH" during installation.
    echo.
    echo 2. **Permission denied:**
    echo    Run Command Prompt as Administrator if needed.
    echo.
    echo 3. **Database errors:**
    echo    ```cmd
    echo    python manage.py migrate
    echo    ```
    echo.
    echo 4. **Port already in use:**
    echo    Change the port in run.bat or kill the process using port 8000.
    echo.
    echo ### File Structure
    echo.
    echo ```
    echo automoto/
    echo ├── setup_windows.bat      # This setup script
    echo ├── run.bat                # Development run script
    echo ├── test_app.bat           # Test script
    echo ├── test_app.py            # Python test script
    echo ├── requirements.txt        # Python dependencies
    echo ├── .env                   # Environment variables
    echo └── SETUP_README.md        # This file
    echo ```
    echo.
    echo ## Next Steps
    echo.
    echo 1. Update the SECRET_KEY in .env for production
    echo 2. Configure your database settings
    echo 3. Set up proper logging
    echo 4. Consider using IIS or Apache for production
) > SETUP_README.md

echo.
echo [SUCCESS] Windows setup complete!
echo.
echo 🎉 AutoMoto Job Scraper is ready to use!
echo.
echo 📋 Next steps:
echo 1. Test the setup: test_app.bat
echo 2. Run the app: run.bat
echo 3. Open browser: http://localhost:8000
echo 4. Admin panel: http://localhost:8000/admin ^(admin/admin123^)
echo.
echo 📚 For more information, see SETUP_README.md
echo.
pause 