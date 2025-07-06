#!/usr/bin/env python3
"""
Test script to verify EasyApply filtering functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'automoto.settings')
django.setup()

from job_scraper.enhanced_scrapers import EnhancedJobScraper
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_easyapply_filtering():
    """Test the EasyApply filtering functionality"""
    scraper = EnhancedJobScraper()
    
    print("Testing EasyApply filtering for LinkedIn jobs...")
    print("=" * 50)
    
    # Test with a small number of pages to avoid overwhelming the servers
    jobs = scraper.get_recent_jobs(
        websites=['linkedin'],
        country='us',
        keywords='python developer',
        max_pages=1
    )
    
    print(f"Total jobs found: {len(jobs)}")
    print(f"Jobs after EasyApply filtering: {len(jobs)}")
    
    if jobs:
        print("\nSample job details:")
        for i, job in enumerate(jobs[:3]):  # Show first 3 jobs
            print(f"\nJob {i+1}:")
            print(f"  Title: {job.get('title', 'N/A')}")
            print(f"  Company: {job.get('company', 'N/A')}")
            print(f"  Location: {job.get('location', 'N/A')}")
            print(f"  Application Link: {job.get('application_link', 'N/A')}")
            print(f"  Source: {job.get('source_website', 'N/A')}")
    else:
        print("No jobs found or all jobs were filtered out.")
    
    print("\n" + "=" * 50)
    print("EasyApply filtering test completed!")

if __name__ == "__main__":
    test_easyapply_filtering() 