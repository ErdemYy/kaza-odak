# start_saferoute.ps1 ile başlatılan SafeRoute 3D sunucusunu durdurur. Depo kökünden:
#   powershell -ExecutionPolicy Bypass -File scripts\stop_saferoute.ps1
# Yalnızca .saferoute\server.pid içinde kayıtlı VE komut satırı "saferoute ... serve" olan süreç (ve onun
# laboratuvar çalışanları) durdurulur; başka projelerin süreçlerine dokunulmaz.
# Not: süreç dışarıdan sonlandırıldığında yarım kalan laboratuvar işleri bir sonraki açılışta "Yarıda kaldı"
# olarak işaretlenir (otomatik yeniden çalıştırılmaz); tamamlanmış sonuçlar diskte korunur.
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PidFile = Join-Path $Root ".saferoute\server.pid"

if (-not (Test-Path $PidFile)) {
    Write-Host "Kayıtlı SafeRoute sunucusu yok (.saferoute\server.pid bulunamadı). Ön planda çalışıyorsa o pencerede Ctrl+C kullanın."
    exit 0
}
$serverPid, $port = (Get-Content $PidFile -Raw).Trim().Split("|")
$p = Get-CimInstance Win32_Process -Filter "ProcessId = $serverPid" -ErrorAction SilentlyContinue
if (-not $p) {
    Write-Host "Kayıtlı süreç (PID $serverPid) zaten çalışmıyor; kayıt temizlendi."
    Remove-Item $PidFile -ErrorAction SilentlyContinue
    exit 0
}
if ($p.CommandLine -notmatch "saferoute" -or $p.CommandLine -notmatch "\bserve\b") {
    Write-Host "PID $serverPid artık SafeRoute sunucusu değil ($($p.Name)); DOKUNULMADI. Kayıt temizlendi." -ForegroundColor Yellow
    Remove-Item $PidFile -ErrorAction SilentlyContinue
    exit 1
}
# Önce alt süreçler (uvicorn çalışan / laboratuvar çalışanı), sonra sunucu
$children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $serverPid" -ErrorAction SilentlyContinue)
foreach ($c in $children) {
    $grand = @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $($c.ProcessId)" -ErrorAction SilentlyContinue)
    foreach ($g in $grand) { Stop-Process -Id $g.ProcessId -Force -ErrorAction SilentlyContinue }
    Stop-Process -Id $c.ProcessId -Force -ErrorAction SilentlyContinue
}
Stop-Process -Id $serverPid -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 800
$left = @(Get-Process -Id (@([int]$serverPid) + ($children | ForEach-Object { [int]$_.ProcessId })) -ErrorAction SilentlyContinue)
Remove-Item $PidFile -ErrorAction SilentlyContinue
if ($left.Count -gt 0) {
    Write-Host "Bazı süreçler hâlâ çalışıyor: $($left.Id -join ', ')" -ForegroundColor Red
    exit 1
}
Write-Host "SafeRoute sunucusu durduruldu (PID $serverPid, port $port)." -ForegroundColor Green
