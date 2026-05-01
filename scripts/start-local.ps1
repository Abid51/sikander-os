# Sikander OS - start API + Vite (two windows on Windows)
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
Set-Location $root

Write-Host "Syncing backend dependencies (pip)..."
Push-Location $backend
python -m pip install -q -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "pip install failed - fix errors above, then retry."
    Pop-Location
    exit 1
}
Pop-Location

Write-Host "Starting backend on :8000 ..."
Start-Process pwsh -ArgumentList @(
  "-NoExit", "-Command",
  "Set-Location '$backend'; python main.py"
)

Start-Sleep -Seconds 2

Write-Host "Starting frontend on :5173 ..."
Set-Location "$root\frontend"
npm run dev
