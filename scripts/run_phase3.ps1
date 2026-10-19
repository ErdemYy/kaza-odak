# Faz 3 kümeleme hattını çalıştırır (Windows PowerShell). Depo kökünden çalıştırın:
#   powershell -ExecutionPolicy Bypass -File scripts\run_phase3.ps1
# Kayıtlı başarılı deneyler yeniden çalıştırılmaz; --force bilerek kullanılmaz.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$env:PYTHONIOENCODING = "utf-8"
$py = "backend\.venv\Scripts\python.exe"
$sr = "backend\.venv\Scripts\saferoute.exe"

function Invoke-Step([string]$exe, [string[]]$arguments) {
    & $exe @arguments
    if ($LASTEXITCODE -ne 0) { throw "Adım başarısız: $exe $($arguments -join ' ') (çıkış $LASTEXITCODE)" }
}

Invoke-Step $sr @("cluster")
Invoke-Step $py @("scripts\execute_notebook.py", "notebooks\03_clustering_experiments.ipynb")
Push-Location backend
try { Invoke-Step ".venv\Scripts\python.exe" @("-m", "pytest", "-q") } finally { Pop-Location }
