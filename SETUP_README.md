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
