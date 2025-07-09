#!/usr/bin/env python3
"""
Test script to verify AutoMoto Job Scraper setup
"""

import os
import sys


def test_imports():
    """Test that all required packages can be imported"""
    print("🧪 Testing AutoMoto Job Scraper imports...")
    print("=" * 50)

    # Test core dependencies
    try:
        import django

        print(f"✅ Django {django.get_version()}")
    except ImportError as e:
        print(f"❌ Django import failed: {e}")
        return False

    try:
        import requests

        print(f"✅ requests {requests.__version__}")
    except ImportError as e:
        print(f"❌ requests import failed: {e}")
        return False

    try:
        from bs4 import BeautifulSoup

        print("✅ beautifulsoup4")
    except ImportError as e:
        print(f"❌ beautifulsoup4 import failed: {e}")
        return False

    try:
        import html5lib

        print(f"✅ html5lib {html5lib.__version__}")
    except ImportError as e:
        print(f"❌ html5lib import failed: {e}")
        return False

    try:
        import dotenv

        print("✅ python-dotenv")
    except ImportError as e:
        print(f"❌ python-dotenv import failed: {e}")
        return False

    try:
        import pytest

        print(f"✅ pytest {pytest.__version__}")
    except ImportError as e:
        print(f"❌ pytest import failed: {e}")
        return False

    # Test development tools (optional)
    try:
        import black

        print(f"✅ black {black.__version__}")
    except ImportError:
        print("⚠️  black not installed (development dependency)")

    try:
        import autopep8

        print("✅ autopep8")
    except ImportError:
        print("⚠️  autopep8 not installed (development dependency)")

    try:
        import isort

        print(f"✅ isort {isort.__version__}")
    except ImportError:
        print("⚠️  isort not installed (development dependency)")

    # Test Django setup
    try:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "automoto.settings")
        django.setup()
        print("✅ Django setup successful")
    except Exception as e:
        print(f"❌ Django setup failed: {e}")
        return False

    # Test project-specific imports
    try:
        from job_scraper.models import CustomWebsite, Job

        print("✅ Project models imported successfully")
    except Exception as e:
        print(f"❌ Project models import failed: {e}")
        return False

    try:
        from job_scraper.enhanced_scrapers import EnhancedJobScraper

        print("✅ Enhanced scraper imported successfully")
    except Exception as e:
        print(f"❌ Enhanced scraper import failed: {e}")
        return False

    print("=" * 50)
    print("🎉 All core imports successful!")
    return True


if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
