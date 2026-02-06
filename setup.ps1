# Setup script for Windows PowerShell
Write-Host "Starting setup for NBA Fantasy Team Builder Agent..." -ForegroundColor Cyan

# 1. Setup Backend
Write-Host "Setting up backend..." -ForegroundColor Yellow
cd backend
if (-not (Test-Path "venv")) {
    python -m venv venv
    Write-Host "Virtual environment created." -ForegroundColor Green
}

# Activate venv and install requirements
& .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd ..

# 2. Setup Frontend
Write-Host "Setting up frontend..." -ForegroundColor Yellow
cd frontend
npm install
cd ..

Write-Host "Setup complete! You can now run the app using './run.ps1'" -ForegroundColor Green
