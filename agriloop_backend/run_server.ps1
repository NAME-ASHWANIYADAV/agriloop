$ErrorActionPreference = "Stop"

$VenvPath = ".\venv\Scripts\Activate.ps1"
if (Test-Path $VenvPath) {
    Write-Host "Activating virtual environment..."
    . $VenvPath
} else {
    Write-Error "Virtual environment not found at $VenvPath. Please run 'python -m venv venv' first."
}

Write-Host "Starting AgriLoop Backend Server..."
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
