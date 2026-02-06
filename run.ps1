# Run script for Windows PowerShell
$scripts = @()

Write-Host "Starting NBA Fantasy Team Builder Agent..." -ForegroundColor Cyan

# Define the commands
$backendCommand = "cd backend; .\venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --port 8000"
$frontendCommand = "cd frontend; npm run dev"

# Start both in new jobs or just run them
Write-Host "Starting FastAPI backend and Vite frontend..." -ForegroundColor Yellow

# Using Start-Process to open them in new windows is often easier for local dev
# but if we want a "one command" in the same terminal, we can use jobs.
# However, for a better dev experience, we'll use a simple approach:

Start-Process powershell -ArgumentList "-NoExit", "-Command", "$backendCommand"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "$frontendCommand"

Write-Host "Both servers are starting in new windows!" -ForegroundColor Green
Write-Host "Backend: http://localhost:8000"
Write-Host "Frontend: http://localhost:5173"
