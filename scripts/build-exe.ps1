# Build a self-contained Windows executable for hsm-sync.
#
# Prerequisites (on your build machine — NOT required on the server):
#   uv installed: https://docs.astral.sh/uv/getting-started/installation/
#   Run this script from the repo root.
#
# Output: dist\hsm-sync.exe  (~20-40 MB, no external dependencies)
#
# Deploy: copy dist\hsm-sync.exe to Server A alongside .env, then register
# taskscheduler\hsm-sync.xml with Task Scheduler.

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "Syncing dependencies..." -ForegroundColor Cyan
uv sync

Write-Host "Building hsm-sync.exe..." -ForegroundColor Cyan
uv run pyinstaller `
    --onefile `
    --name hsm-sync `
    --collect-all python_dotenv `
    src\hsm_sync\main.py

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller failed (exit $LASTEXITCODE)"
    exit $LASTEXITCODE
}

$exe = "dist\hsm-sync.exe"
$size = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host "Built: $exe ($size MB)" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Copy $exe to Server A (e.g. C:\hsm-sync\hsm-sync.exe)"
Write-Host "  2. Copy .env.example to Server A as C:\hsm-sync\.env and fill in values"
Write-Host "  3. Import taskscheduler\hsm-sync.xml into Task Scheduler"
Write-Host "     schtasks /Create /XML taskscheduler\hsm-sync.xml /TN 'HSM Sync' /RU 'DOMAIN\deploy' /RP"
