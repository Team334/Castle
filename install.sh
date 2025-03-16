#!/bin/bash

echo "Setting up the Scouting-App..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Python is not installed! Please install Python 3.7+ and try again."
    exit 1
fi

# Create and activate virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "Installing required packages..."
pip install -r requirements.txt

echo ""
echo "Installation complete! You can now run the app with:"
echo "    python app/main.py"
echo ""
echo "Don't forget to set up your environment variables if needed."

# Make the script executable
chmod +x app/main.py
