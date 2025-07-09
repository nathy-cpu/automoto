#!/bin/bash
# Run script for AutoMoto Job Scraper

# Activate virtual environment
source venv/bin/activate

# Run Django development server
python manage.py runserver 0.0.0.0:8000
