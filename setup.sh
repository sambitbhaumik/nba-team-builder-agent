#!/bin/bash

# Exit on error
set -e

echo "Starting setup for NBA Fantasy Team Builder Agent..."

# 1. Setup Backend
echo "Setting up backend..."
cd backend
if [ ! -d "venv" ]; then
    python -m venv venv
    echo "Virtual environment created."
fi

# Activate venv and install requirements
source venv/Scripts/activate || source venv/bin/activate
pip install -r requirements.txt
cd ..

# 2. Setup Frontend
echo "Setting up frontend..."
cd frontend
npm install
cd ..

echo "Setup complete! You can now run the app using './run.sh'"
