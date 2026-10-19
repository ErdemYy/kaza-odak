# Faz 1 hattını uçtan uca çalıştırır (Windows PowerShell). Depo kökünden çalıştırın:
#   powershell -ExecutionPolicy Bypass -File scripts\run_phase1.ps1
# Mevcut tam bir anlık görüntü varsa indirme atlanır; zorlamak için -ForceDownload.
param([switch]$ForceDownload)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$env:PYTHONIOENCODING = "utf-8"
$py = "backend\.venv\Scripts\python.exe"
$sr = "backend\.venv\Scripts\saferoute.exe"

function Invoke-Step([string]$exe, [string[]]$arguments) {
    & $exe @arguments
    if ($LASTEXITCODE -ne 0) { throw "Adım başarısız: $exe $($arguments -join ' ') (çıkış $LASTEXITCODE)" }
}

& $sr check-source
if ($LASTEXITCODE -ne 0) { Write-Warning "Kaynak erişilemedi; mevcut anlık görüntüyle devam ediliyor." }

$hasSnapshot = Test-Path "data\raw\h9gi-nx95\snapshot_*\manifest.json"
if ($ForceDownload -or -not $hasSnapshot) { Invoke-Step $sr @("download") }

Invoke-Step $sr @("verify")
Invoke-Step $sr @("record")
Invoke-Step $sr @("parquet")
Invoke-Step $sr @("eda")
Invoke-Step $py @("scripts\execute_notebook.py", "notebooks\01_dataset_exploration.ipynb")
Push-Location backend
try { Invoke-Step ".venv\Scripts\python.exe" @("-m", "pytest", "-q") } finally { Pop-Location }
