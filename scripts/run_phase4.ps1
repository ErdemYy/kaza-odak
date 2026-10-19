# Faz 4 hattını çalıştırır (Windows PowerShell). Depo kökünden:
#   powershell -ExecutionPolicy Bypass -File scripts\run_phase4.ps1
# Faz 3 çıktıları mevcut olmalıdır (saferoute cluster). Harita karoları için ağ erişimi gerekir.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$env:PYTHONIOENCODING = "utf-8"
$sr = "backend\.venv\Scripts\saferoute.exe"

function Invoke-Step([string]$exe, [string[]]$arguments) {
    & $exe @arguments
    if ($LASTEXITCODE -ne 0) { throw "Adım başarısız: $exe $($arguments -join ' ') (çıkış $LASTEXITCODE)" }
}

Invoke-Step $sr @("viz-build")
Push-Location frontend
try {
    Invoke-Step "npm.cmd" @("ci")
    Invoke-Step "npm.cmd" @("run", "build")
    Invoke-Step "npm.cmd" @("test")
    Invoke-Step "npx.cmd" @("playwright", "install", "chromium-headless-shell")
    Invoke-Step "npm.cmd" @("run", "e2e")   # sunucu çalışmıyorsa Playwright 'saferoute serve' başlatır
} finally { Pop-Location }
Push-Location backend
try { Invoke-Step ".venv\Scripts\python.exe" @("-m", "pytest", "-q") } finally { Pop-Location }
Write-Host "Görüntüleyici: $sr serve  ->  http://127.0.0.1:8000"
