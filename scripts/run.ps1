$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$BaseDir = Split-Path -Parent $PSScriptRoot

Write-Host "Starting Autostack..." -ForegroundColor Green

# 1. Check if Docker is running
docker info > $null 2>&1
if ($LastExitCode -ne 0) {
    Write-Host "Error: Docker is not running. Please start Docker and try again." -ForegroundColor Red
    exit 1
}

# 2. Check for .env file
if (-not (Test-Path "$BaseDir\autostack-engine\.env")) {
    Write-Host "Warning: .env file missing in autostack-engine. Running setup first..." -ForegroundColor Yellow
    & "$PSScriptRoot\setup_autostack.sh" # Assuming bash/zsh environment or that they have a way to run .sh
}

# 3. Check for GEMINI_API_KEY
$envFile = Get-Content "$BaseDir\autostack-engine\.env"
if ($envFile -match "GEMINI_API_KEY=$" -or $envFile -match "GEMINI_API_KEY=\s*$") {
    Write-Host "Warning: GEMINI_API_KEY is not set in autostack-engine\.env" -ForegroundColor Yellow
    Write-Host "The application may not function correctly without it." -ForegroundColor Yellow
    Write-Host "Press Ctrl+C to stop and add it, or wait 5 seconds to continue anyway..."
    Start-Sleep -Seconds 5
}

# 4. Start Docker Services
Write-Host "Starting Docker services..." -ForegroundColor Green
cd "$BaseDir\autostack-engine"
docker compose --env-file .env -f deployments/docker/compose.yml up -d

# 5. Start Backend and Frontend simultaneously
Write-Host "Launching Services..." -ForegroundColor Green
Write-Host "Backend running on port 8000 (Proxy/Gateway)"
Write-Host "Frontend running on http://localhost:4200"

# Start backend gateway in background
Start-Process -NoNewWindow -FilePath "python" -ArgumentList "-m poetry run gateway"

# Start frontend in foreground
cd "$BaseDir\autostack"
npm start
