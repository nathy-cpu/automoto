#!/bin/bash

# Universal Setup Script for AutoMoto Job Scraper
# This script detects the operating system and runs the appropriate setup

set -e  # Exit on any error

echo "🚀 AutoMoto Job Scraper - Universal Setup"
echo "=========================================="

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

# Detect operating system
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
        echo "windows"
    else
        echo "unknown"
    fi
}

# Get OS
OS=$(detect_os)
print_status "Detected operating system: $OS"

# Check if appropriate setup script exists
case $OS in
    "linux")
        if [ -f "setup_linux.sh" ]; then
            print_status "Found Linux setup script"
            chmod +x setup_linux.sh
            ./setup_linux.sh
        else
            print_error "Linux setup script not found"
            exit 1
        fi
        ;;
    "macos")
        if [ -f "setup_macos.sh" ]; then
            print_status "Found macOS setup script"
            chmod +x setup_macos.sh
            ./setup_macos.sh
        else
            print_error "macOS setup script not found"
            exit 1
        fi
        ;;
    "windows")
        if [ -f "setup_windows.bat" ]; then
            print_status "Found Windows setup script"
            print_warning "Please run setup_windows.bat directly on Windows"
            print_warning "This universal script cannot run Windows batch files"
            exit 1
        else
            print_error "Windows setup script not found"
            exit 1
        fi
        ;;
    *)
        print_error "Unsupported operating system: $OS"
        print_status "Please run the appropriate setup script manually:"
        echo "  - Linux: ./setup_linux.sh"
        echo "  - macOS: ./setup_macos.sh"
        echo "  - Windows: setup_windows.bat"
        exit 1
        ;;
esac

print_success "Setup completed successfully!"
echo ""
echo "🎉 AutoMoto Job Scraper is ready to use!"
echo ""
echo "📋 Next steps:"
echo "1. Test the setup: python test_app.py"
echo "2. Run the app: ./run.sh (Linux/macOS) or run.bat (Windows)"
echo "3. Open browser: http://localhost:8000"
echo "4. Admin panel: http://localhost:8000/admin (admin/admin123)"
echo ""
echo "📚 For more information, see README.md"
echo "" 