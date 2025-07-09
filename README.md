# AutoMoto Job Scraper

A powerful Django web application for scraping job listings from multiple websites with advanced filtering capabilities, including EasyApply detection for LinkedIn jobs.

## 🚀 Features

- **Multi-Site Job Scraping**: Scrape jobs from Indeed, LinkedIn, Glassdoor, Monster, CareerBuilder, and ZipRecruiter
- **EasyApply Filtering**: Automatically filter out LinkedIn jobs that use EasyApply for better quality opportunities
- **Custom Website Support**: Add and manage custom job websites with CSS selectors
- **Advanced Job Details**: Extract comprehensive job information including direct application links
- **Modern UI**: Beautiful, responsive web interface with loading animations
- **Pagination**: Navigate through large result sets efficiently
- **Admin Panel**: Manage custom websites and application settings

## 📋 Prerequisites

- Python 3.8 or higher
- Git
- Internet connection for scraping

## 🛠️ Quick Setup

### Linux
```bash
# Make the script executable
chmod +x setup_linux.sh

# Run the setup script
./setup_linux.sh

# Test the setup
python test_app.py

# Run the application
./run.sh
```

### Windows
```cmd
# Run the setup script
setup_windows.bat

# Test the setup
test_app.bat

# Run the application
run.bat
```

### macOS
```bash
# Make the script executable
chmod +x setup_macos.sh

# Run the setup script
./setup_macos.sh

# Test the setup
python test_app.py

# Run the application
./run.sh
```

## 🌐 Access the Application

After running the setup script:

1. **Main Application**: http://localhost:8000
2. **Admin Panel**: http://localhost:8000/admin
   - Username: `admin`
   - Password: `admin123`

## 🔧 Manual Setup (Alternative)

If you prefer to set up manually:

### 1. Clone the Repository
```bash
git clone <repository-url>
cd automoto
```

### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

**For development (recommended):**
```bash
pip install -r requirements-dev.txt
```

**For runtime only:**
```bash
pip install -r requirements.txt
```

**For production:**
```bash
pip install -r requirements-prod.txt
```

### 4. Configure Environment
Create a `.env` file:
```env
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=sqlite:///db.sqlite3
SCRAPING_DELAY=2
MAX_PAGES_PER_SITE=5
REQUEST_TIMEOUT=30
LOG_LEVEL=INFO
```

### 5. Run Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Create Superuser
```bash
python manage.py createsuperuser
```

### 7. Run the Application
```bash
python manage.py runserver
```

## 📊 Supported Job Sites

### Built-in Sites
- **Indeed**: Comprehensive job listings with detailed information
- **LinkedIn**: Professional networking jobs (with EasyApply filtering)
- **Glassdoor**: Company reviews and job listings
- **Monster**: Traditional job board
- **CareerBuilder**: Large job database
- **ZipRecruiter**: AI-powered job matching

### Custom Sites
Add your own job websites with CSS selectors for:
- Job title extraction
- Company name extraction
- Location extraction
- Salary information
- Posted date
- Job description
- Application links

## 🎯 EasyApply Filtering

The application automatically filters out LinkedIn jobs that use EasyApply, focusing on jobs that require traditional application processes. This helps find:

- **Better Quality Jobs**: Traditional applications often indicate more serious opportunities
- **More Detailed Information**: Better job descriptions and requirements
- **Direct Application Links**: Direct links to company application systems
- **Reduced Noise**: Eliminates low-effort job postings

### Filtered Indicators
- `easy apply`, `easyapply`
- `quick apply`, `one-click apply`
- `apply with linkedin`, `apply with profile`
- And 10+ other variations

## 🏗️ Production Deployment

### Linux (systemd)
```bash
./setup_production.sh
sudo systemctl start automoto
sudo systemctl enable automoto
```

### macOS (launchd)
```bash
./setup_production.sh
launchctl load ~/Library/LaunchAgents/com.automoto.jobscraper.plist
```

### Windows
Consider using IIS or Apache with mod_wsgi for production deployment.

## 🔍 Testing

### Test the Setup
```bash
python test_setup.py
```

### Test EasyApply Filtering
```bash
python test_easyapply_filter.py
```

### Run Django Tests
```bash
python manage.py test
```

## 🎨 Code Formatting

The project uses several tools to ensure PEP8 compliance and consistent code formatting:

### Install Development Dependencies
```bash
pip install -r requirements-dev.txt
```

### Format Code with Black
```bash
# Format all Python files
black .

# Check formatting without making changes
black . --check
```

### Sort Imports with isort
```bash
# Sort imports in all Python files
isort .

# Check import sorting without making changes
isort . --check-only
```

### Fix PEP8 Issues with autopep8
```bash
# Fix PEP8 issues in all Python files
autopep8 --in-place --recursive .

# Show what would be changed without making changes
autopep8 --diff --recursive .
```

### Complete Formatting Workflow
```bash
# 1. Sort imports
isort .

# 2. Format with Black
black .

# 3. Fix PEP8 issues
autopep8 --in-place --recursive .
```

## 📁 Project Structure

```