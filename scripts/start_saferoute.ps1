# SafeRoute 3D'yi tek komutla başlatır (Windows PowerShell 5.1+). Depo kökünden:
#   powershell -ExecutionPolicy Bypass -File scripts\start_saferoute.ps1            # ön planda; Ctrl+C ile durur
#   powershell -ExecutionPolicy Bypass -File scripts\start_saferoute.ps1 -Demo      # akademik demo profili
#   powershell -ExecutionPolicy Bypass -File scripts\start_saferoute.ps1 -Background
#   powershell -ExecutionPolicy Bypass -File scripts\stop_saferoute.ps1             # arka plandaki sunucuyu durdurur
#
# Yaptıkları: bağımlılıkları ve gerekli veri/model dosyalarını denetler, gerekirse ön yüzü derler, sunucuyu başlatır,
# hazır olmasını bekler ve adresi gösterir. Veri setini yeniden İNDİRMEZ, model eğitimini BAŞLATMAZ.
[CmdletBinding()]
param(
    [int]$Port = 8000,
    [switch]$Demo,         # demo profili: kaynak/ağ denetimi, kayıtlı sonuçları ısıtma, demo adımları
    [switch]$Background,   # sunucuyu arka planda başlat (PID: .saferoute\server.pid, günlük: .saferoute\server.log)
    [switch]$Rebuild,      # ön yüzü her durumda yeniden derle
    [switch]$Open          # hazır olunca tarayıcıyı aç
)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root
$env:PYTHONIOENCODING = "utf-8"
$Py = Join-Path $Root "backend\.venv\Scripts\python.exe"
$Sr = Join-Path $Root "backend\.venv\Scripts\saferoute.exe"
$RunDir = Join-Path $Root ".saferoute"
$Url = "http://127.0.0.1:$Port"
$problems = New-Object System.Collections.Generic.List[string]

function Say([string]$msg, [string]$color = "Gray") { Write-Host $msg -ForegroundColor $color }
function Ok([string]$msg) { Say "  [tamam] $msg" "Green" }
function Warn([string]$msg) { Say "  [uyarı] $msg" "Yellow" }
function Fail([string]$msg, [string]$fix) {
    Say "  [HATA]  $msg" "Red"
    if ($fix) { Say "          Çözüm: $fix" "Red" }
    $script:problems.Add($msg) | Out-Null
}
function Get-Json([string]$path, [int]$timeoutSec = 5) {
    try { return Invoke-RestMethod -Uri "$Url$path" -TimeoutSec $timeoutSec -UseBasicParsing } catch { return $null }
}

Say "SafeRoute 3D — başlatma denetimi ($Root)" "Cyan"

# ---------------------------------------------------------------- 1) Python ortamı ve paketler
if (-not (Test-Path $Py)) {
    Fail "Python sanal ortamı yok (backend\.venv)." "cd backend; uv venv .venv; uv pip install -e "".[dev,api]"" --python .venv\Scripts\python.exe"
} else {
    $check = & $Py -c "import sys, importlib.util as u; m=[n for n in ('fastapi','uvicorn','psutil','numpy','pandas','pyarrow','sklearn','pyproj','saferoute') if u.find_spec(n) is None]; print(f'{sys.version_info.major}.{sys.version_info.minor}|' + ','.join(m))" 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $check) {
        Fail "Python yorumlayıcısı çalıştırılamadı ($Py)." "Sanal ortamı yeniden oluşturun (README > Kurulum)."
    } else {
        $ver, $missing = $check.Trim().Split("|")
        if ([version]$ver -lt [version]"3.11") { Fail "Python $ver bulundu; en az 3.11 gerekir." "Python 3.11+ ile sanal ortamı yeniden oluşturun." }
        elseif ($missing) { Fail "Eksik Python paketleri: $missing" "cd backend; uv pip install -e "".[dev,api]"" --python .venv\Scripts\python.exe" }
        else { Ok "Python $ver ve gerekli paketler" }
    }
}

# ---------------------------------------------------------------- 2) Veri ve model dosyaları (yeniden üretilmez)
$dataDir = $null
if (Test-Path $Py) {
    $dataDir = (& $Py -c "from saferoute.clustering.data import processed_dir; print(processed_dir())" 2>$null)
}
if (-not $dataDir) {
    Fail "İşlenmiş veri dizini bulunamadı (data\processed\...)." "Faz 1–4 hatlarını bir kez çalıştırın: scripts\run_phase1.ps1 … run_phase4.ps1 (README)."
} else {
    $dataDir = $dataDir.Trim()
    $required = @(
        @{ p = "crashes_processed.parquet"; what = "Faz 2 işlenmiş kayıtlar"; fix = "saferoute preprocess" },
        @{ p = "phase3\experiments.json"; what = "Faz 3 deney kaydı"; fix = "saferoute cluster" },
        @{ p = "phase3\model_metadata.json"; what = "Faz 3 model seçimi"; fix = "saferoute cluster" },
        @{ p = "phase4\layer_manifest.json"; what = "Faz 4 doğrulanmış harita katmanları"; fix = "saferoute viz-build" }
    )
    foreach ($r in $required) {
        if (Test-Path (Join-Path $dataDir $r.p)) { Ok "$($r.what)" } else { Fail "$($r.what) yok: $($r.p)" "backend\.venv\Scripts\$($r.fix) (yalnızca bir kez)" }
    }
    $labels = @(Get-ChildItem (Join-Path $dataDir "phase3\labels") -Filter *.npz -ErrorAction SilentlyContinue).Count
    if ($labels -gt 0) { Ok "Faz 3 etiket dosyaları: $labels" } else { Warn "Faz 3 etiket dosyası yok; kayıtlı deneyler haritada açılamaz." }
}
if (Test-Path (Join-Path $Root "frontend\public\models\registry.json")) { Ok "3D varlık kaydı (GLB, lisanslar)" }
else { Fail "frontend\public\models\registry.json yok (GLB varlıkları)." "cd frontend; npm run assets" }

# ---------------------------------------------------------------- 3) Ön yüz derlemesi (gerekirse)
$dist = Join-Path $Root "frontend\dist\index.html"
$needBuild = $Rebuild -or -not (Test-Path $dist)
if (-not $needBuild) {
    $built = (Get-Item $dist).LastWriteTimeUtc
    $newer = Get-ChildItem (Join-Path $Root "frontend\src") -Recurse -File | Where-Object { $_.LastWriteTimeUtc -gt $built } | Select-Object -First 1
    if ($newer) { $needBuild = $true; Say "  Ön yüz kaynakları derlemeden yeni ($($newer.Name)); yeniden derlenecek." }
}
if ($needBuild -and $problems.Count -eq 0) {
    $node = Get-Command node.exe -ErrorAction SilentlyContinue
    if (-not $node) { Fail "Ön yüz derlenmeli ama Node.js bulunamadı." "Node.js 20+ kurun (https://nodejs.org) veya derlenmiş frontend\dist klasörünü kullanın." }
    else {
        $nv = (& node.exe --version).TrimStart("v")
        if ([version]$nv -lt [version]"20.0") { Fail "Node.js $nv bulundu; en az 20 gerekir." "Node.js 20+ kurun." }
        else {
            Push-Location (Join-Path $Root "frontend")
            try {
                if (-not (Test-Path "node_modules")) { Say "  npm ci (ilk kurulum)…"; & npm.cmd ci; if ($LASTEXITCODE -ne 0) { throw "npm ci başarısız" } }
                Say "  Ön yüz derleniyor (npm run build)…"
                & npm.cmd run build
                if ($LASTEXITCODE -ne 0) { throw "npm run build başarısız (çıkış $LASTEXITCODE)" }
                Ok "Ön yüz derlendi"
            } catch { Fail "Ön yüz derlenemedi: $_" "frontend klasöründe 'npm ci' ve 'npm run build' çıktısını inceleyin." }
            finally { Pop-Location }
        }
    }
} elseif (-not $needBuild) { Ok "Derlenmiş ön yüz güncel (frontend\dist)" }

# ---------------------------------------------------------------- 4) Kaynak ve ağ (bilgi)
$os = Get-CimInstance Win32_OperatingSystem
$freeMb = [int]($os.FreePhysicalMemory / 1024)
$totalMb = [int]($os.TotalVisibleMemorySize / 1024)
$minRun = if ($Demo) { 2500 } else { 1200 }
if ($freeMb -lt $minRun) {
    Warn "Boş fiziksel bellek $freeMb MB / $totalMb MB. Sunucu ~450–900 MB kullanır; dinamik analiz için en az 1.500 MB boş bellek gerekir. Diğer uygulamaları kapatmanız önerilir."
} else { Ok "Boş fiziksel bellek $freeMb MB / $totalMb MB" }
$online = $false
try { $null = Invoke-WebRequest -Uri "https://tiles.openfreemap.org/planet" -Method Head -TimeoutSec 5 -UseBasicParsing; $online = $true } catch { }
if ($online) { Ok "Harita karo sağlayıcısına (OpenFreeMap) erişiliyor" }
else { Warn "OpenFreeMap'e ulaşılamadı: altlık harita, bina ve yol karoları İNTERNET gerektirir. Kaza katmanları, kümeler ve tüm analiz ekranları yerel sunucudan çalışmaya devam eder." }

if ($problems.Count -gt 0) {
    Say ""
    Say "Başlatılamadı: $($problems.Count) sorun yukarıda listelendi." "Red"
    exit 1
}

# ---------------------------------------------------------------- 5) Port ve mevcut sunucu
$health = Get-Json "/api/health" 2
if ($health -and $health.status -eq "ok") {
    Say ""
    Say "SafeRoute zaten çalışıyor: $Url (model $($health.experiment_id))." "Cyan"
    Say "Durdurmak için: powershell -ExecutionPolicy Bypass -File scripts\stop_saferoute.ps1 (veya çalıştığı pencerede Ctrl+C)"
    if ($Open) { Start-Process $Url }
    exit 0
}
$busy = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($busy) {
    $owner = (Get-Process -Id $busy.OwningProcess -ErrorAction SilentlyContinue).ProcessName
    Say "Port $Port başka bir uygulama tarafından kullanılıyor ($owner, PID $($busy.OwningProcess)). O sürece dokunulmadı." "Red"
    Say "Başka bir port deneyin: scripts\start_saferoute.ps1 -Port 8010" "Red"
    exit 1
}

# ---------------------------------------------------------------- 6) Sunucuyu başlat
New-Item -ItemType Directory -Force $RunDir | Out-Null
$serveArgs = @("serve", "--port", "$Port")

function Wait-Ready([System.Diagnostics.Process]$proc) {
    $deadline = (Get-Date).AddSeconds(120)
    while ((Get-Date) -lt $deadline) {
        if ($proc -and $proc.HasExited) { return $false }
        $st = Get-Json "/api/analytics/status" 2
        if ($st -and $st.ready) { return $st }
        if ($st -and $st.error -and -not $st.loading) { return $st }
        Start-Sleep -Milliseconds 500
    }
    return $null
}

function Show-Ready($st) {
    Say ""
    Say "SafeRoute 3D hazır:  $Url" "Green"
    Say ("  Olay deposu: {0:N0} olay · yükleme {1} sn" -f $st.n_events, $st.load_seconds)
    $rec = $st.job_recovery
    if ($rec -and $rec.interrupted.Count -gt 0) {
        Warn "Önceki oturumdan yarıda kalan $($rec.interrupted.Count) laboratuvar işi 'Yarıda kaldı' olarak işaretlendi (otomatik yeniden çalıştırılmadı; Laboratuvar > İş geçmişi > Yeniden dene)."
    }
    if ($rec -and $rec.recovered_completed.Count -gt 0) { Ok "Diskte doğrulanan $($rec.recovered_completed.Count) iş sonucu kurtarıldı." }
    if (-not $online) { Warn "Çevrimdışı: altlık harita görünmeyecek; veri katmanları ve analizler çalışır." }
}

function Warm-Demo {
    # Demo profili: kayıtlı sonuçları önceden yükler (ilk tıklamada bekleme olmasın). Model EĞİTİLMEZ.
    Say "  Demo ısıtması: genel bakış, karşılaştırma ve seçili üç modelin kayıtlı sonuçları yükleniyor…"
    $t0 = Get-Date
    $null = Get-Json "/api/overview" 30
    $null = Get-Json "/api/models/comparison" 30
    $null = Get-Json "/api/data/dictionary" 30
    $meta = Get-Json "/api/experiments" 30
    if ($meta -and $meta.selected) {
        foreach ($a in @("dbscan", "kmeans", "hdbscan")) {
            $eid = $meta.selected.$a.experiment_id
            if ($eid) { $null = Get-Json "/api/results/$eid/summary" 60; $null = Get-Json "/api/results/$eid/clusters" 60 }
        }
    }
    $res = Get-Json "/api/lab/resources" 5
    Ok ("Demo ısıtması {0:N1} sn" -f ((Get-Date) - $t0).TotalSeconds)
    if ($res -and -not $res.can_start) { Warn "Boş bellek dinamik analiz için yetersiz ($([int]$res.available_memory_mb) MB). Demoda yalnızca kayıtlı deneyleri gösterin." }
    elseif ($res) { Ok "Dinamik analiz için kaynak uygun (boş $([int]$res.available_memory_mb) MB, çalışan tavanı $($res.worker_memory_limit_mb) MB)" }
    Say ""
    Say "Demo senaryosu: docs\phase6\DEMO_TEST_PLANI.md (14 adım). Önerilen küçük dinamik analiz: DBSCAN, eps 35 m, min_samples 15, filtre Manhattan + 2018." "Cyan"
}

if ($Background) {
    $log = Join-Path $RunDir "server.log"
    $proc = Start-Process -FilePath $Sr -ArgumentList $serveArgs -WorkingDirectory $Root -WindowStyle Hidden `
        -RedirectStandardOutput $log -RedirectStandardError (Join-Path $RunDir "server.err.log") -PassThru
    Set-Content -Path (Join-Path $RunDir "server.pid") -Value "$($proc.Id)|$Port" -Encoding ascii
    Say "  Sunucu arka planda başlatıldı (PID $($proc.Id)); hazır olması bekleniyor…"
    $st = Wait-Ready $proc
    if (-not $st -or -not $st.ready) {
        Say "Sunucu hazır olmadı. Günlükler: $RunDir\server.log, server.err.log" "Red"
        if ($st -and $st.error) { Say "  Hata: $($st.error)" "Red" }
        exit 1
    }
    Show-Ready $st
    if ($Demo) { Warm-Demo }
    Say "Durdurmak için: powershell -ExecutionPolicy Bypass -File scripts\stop_saferoute.ps1"
    if ($Open) { Start-Process $Url }
    exit 0
}

# Ön plan: sunucu bu pencerede çalışır (günlük çıktısı burada görünür).
Say "  Sunucu başlatılıyor (bu pencerede; durdurmak için Ctrl+C)…"
$proc = Start-Process -FilePath $Sr -ArgumentList $serveArgs -WorkingDirectory $Root -NoNewWindow -PassThru
Set-Content -Path (Join-Path $RunDir "server.pid") -Value "$($proc.Id)|$Port" -Encoding ascii
try {
    $st = Wait-Ready $proc
    if ($st -and $st.ready) {
        Show-Ready $st
        if ($Demo) { Warm-Demo }
        if ($Open) { Start-Process $Url }
        Say "Durdurmak için Ctrl+C."
    } elseif (-not $proc.HasExited) {
        Warn "Sunucu 120 sn içinde hazır olmadı; günlük çıktısını inceleyin."
    }
    $proc.WaitForExit()
    if ($proc.ExitCode -ne 0) { Say "Sunucu hata ile sonlandı (çıkış $($proc.ExitCode))." "Red"; exit $proc.ExitCode }
} finally {
    if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -ErrorAction SilentlyContinue }
    Remove-Item (Join-Path $RunDir "server.pid") -ErrorAction SilentlyContinue
}
