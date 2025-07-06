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
```bash
pip install -r requirements.txt
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
python test_app.py
```

### Test EasyApply Filtering
```bash
python test_easyapply_filter.py
```

### Run Django Tests
```bash
python manage.py test
```

## 📁 Project Structure

```
automoto/
├── automoto/                 # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── job_scraper/             # Main application
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   ├── enhanced_scrapers.py
│   └── templates/
├── setup_linux.sh           # Linux setup script
├── setup_windows.bat        # Windows setup script
├── setup_macos.sh           # macOS setup script
├── requirements.txt          # Python dependencies
├── manage.py                # Django management
└── README.md               # This file
```

## 🛠️ Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DEBUG` | Django debug mode | `True` |
| `SECRET_KEY` | Django secret key | Auto-generated |
| `ALLOWED_HOSTS` | Allowed hostnames | `localhost,127.0.0.1` |
| `DATABASE_URL` | Database connection | `sqlite:///db.sqlite3` |
| `SCRAPING_DELAY` | Delay between requests | `2` |
| `MAX_PAGES_PER_SITE` | Max pages to scrape | `5` |
| `REQUEST_TIMEOUT` | Request timeout | `30` |
| `LOG_LEVEL` | Logging level | `INFO` |

### Custom Website Configuration

Add custom websites through the admin panel with:
- **Name**: Website name
- **Base URL**: Website base URL
- **Search URL**: URL template with placeholders
- **CSS Selectors**: Selectors for job data extraction
- **Active Status**: Enable/disable the website

## 🐛 Troubleshooting

### Common Issues

1. **Permission Denied**
   ```bash
   chmod +x setup_*.sh
   ```

2. **Python Version Issues**
   - Linux: Script installs Python 3.9 if needed
   - macOS: Script installs Python 3.9 via Homebrew
   - Windows: Install Python 3.8+ manually

3. **Database Errors**
   ```bash
   python manage.py migrate
   ```

4. **Port Already in Use**
   ```bash
   # Kill process on port 8000
   lsof -ti:8000 | xargs kill -9
   ```

5. **Scraping Issues**
   - Check internet connection
   - Verify website accessibility
   - Check rate limiting settings

### Logs

- **Application Logs**: Check console output
- **Django Logs**: Check console output
- **System Logs**: 
  - Linux: `journalctl -u automoto`
  - macOS: `log show --predicate 'process == "automoto"'`

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section
2. Review the logs
3. Create an issue on GitHub
4. Check the documentation

## 🔄 Updates

To update the application:

1. **Pull latest changes**
   ```bash
   git pull origin main
   ```

2. **Update dependencies**
   ```bash
   pip install -r requirements.txt --upgrade
   ```

3. **Run migrations**
   ```bash
   python manage.py migrate
   ```

4. **Restart the application**
   ```bash
   # Stop current instance
   # Run the application again
   ./run.sh
   ```

---

**Happy Job Hunting! 🎯** 