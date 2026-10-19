# Faz 2 hattını uçtan uca çalıştırır (Windows PowerShell). Depo kökünden çalıştırın:
#   powershell -ExecutionPolicy Bypass -File scripts\run_phase2.ps1 [-Force]
param([switch]$Force)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$env:PYTHONIOENCODING = "utf-8"
$py = "backend\.venv\Scripts\python.exe"
$sr = "backend\.venv\Scripts\saferoute.exe"

function Invoke-Step([string]$exe, [string[]]$arguments) {
    & $exe @arguments
    if ($LASTEXITCODE -ne 0) { throw "Adım başarısız: $exe $($arguments -join ' ') (çıkış $LASTEXITCODE)" }
}

if (-not (Test-Path "data\raw\gthc-hcne\snapshot_*\manifest.json")) { Invoke-Step $sr @("boundaries") }
if ($Force) { Invoke-Step $sr @("preprocess", "--force") } else { Invoke-Step $sr @("preprocess") }
Invoke-Step $py @("scripts\execute_notebook.py", "notebooks\02_preprocessing_feature_engineering.ipynb")
Push-Location backend
try { Invoke-Step ".venv\Scripts\python.exe" @("-m", "pytest", "-q") } finally { Pop-Location }
