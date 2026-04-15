#!/bin/bash
# Format project script for AutoMoto Job Scraper
# Formats all Python files to comply with PEP8 and Black standards

echo "  AutoMoto Job Scraper - Code Formatting"
echo "=========================================="

# Check if required tools are installed
if ! command -v black &> /dev/null; then
    echo "  Black is not installed. Please install development dependencies:"
    echo "pip install -r requirements-dev.txt"
    exit 1
fi

if ! command -v isort &> /dev/null; then
    echo "  isort is not installed. Please install development dependencies:"
    echo "pip install -r requirements-dev.txt"
    exit 1
fi

if ! command -v autopep8 &> /dev/null; then
    echo "  autopep8 is not installed. Please install development dependencies:"
    echo "pip install -r requirements-dev.txt"
    exit 1
fi

echo "  Formatting project..."

# Step 1: Sort imports with isort
echo "  Sorting imports..."
isort .
if [ $? -eq 0 ]; then
    echo "  Imports sorted successfully"
else
    echo "  Import sorting failed"
    exit 1
fi

# Step 2: Format code with Black
echo "  Formatting code with Black..."
black .
if [ $? -eq 0 ]; then
    echo "  Code formatted successfully"
else
    echo "  Code formatting failed"
    exit 1
fi

# Step 3: Fix PEP8 issues with autopep8
echo "  Fixing PEP8 issues..."
autopep8 --in-place --recursive .
if [ $? -eq 0 ]; then
    echo "  PEP8 issues fixed successfully"
else
    echo "  PEP8 fixing failed"
    exit 1
fi

echo ""
echo "  Formatting complete!"
echo ""
echo "  Summary:"
echo "- Imports sorted with isort"
echo "- Code formatted with Black"
echo "- PEP8 issues fixed with autopep8"
echo ""
echo "  To check formatting without making changes:"
echo "  isort . --check-only"
echo "  black . --check"
echo "  autopep8 --diff --recursive ." 