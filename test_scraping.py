#!/usr/bin/env python3
"""
Test script for job scraping functionality
"""

import os
import sys

from job_scraper.scrapers import get_scraper, scrape_jobs

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_scraping():
    """Test the scraping functionality"""
    print("Testing job scraping functionality...")

    # Test parameters
    websites = ["indeed", "linkedin"]
    country = "us"
    keywords = "python developer"

    try:
        # Test scraping
        jobs = scrape_jobs(websites, country, keywords)

        print(f"Successfully scraped {len(jobs)} jobs")

        # Display first few jobs
        for i, job in enumerate(jobs[:3]):
            print(f"\nJob {i+1}:")
            print(f"  Title: {job.get('title', 'N/A')}")
            print(f"  Company: {job.get('company', 'N/A')}")
            print(f"  Location: {job.get('location', 'N/A')}")
            print(f"  Source: {job.get('source_website', 'N/A')}")

        return True

    except Exception as e:
        print(f"Error during scraping: {e}")
        return False


if __name__ == "__main__":
    success = test_scraping()
    sys.exit(0 if success else 1)
