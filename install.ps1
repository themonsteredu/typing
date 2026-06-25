# Exam Studio - Windows installer
# Node 22+, Python 3.10+ 확인/설치 -> 의존성 설치 -> AI CLI(선택) -> 실행 안내

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Have($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

function Refresh-Path {
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path", "User")
}

function Winget-Install($id) {
    if (-not (Have winget)) { throw "winget이 없어 $id 를 자동 설치할 수 없습니다." }
    winget install --id $id -e --source winget --accept-source-agreements --accept-package-agreements
    Refresh-Path
}

# --- Node.js 22+ ---
function Ensure-Node {
    $ok = $false
    if (Have node) {
        $v = (node -v) -replace "v", ""
        if ([int]($v.Split(".")[0]) -ge 22) { $ok = $true }
    }
    if (-not $ok) {
        Write-Step "Node.js 22+ 설치 중..."
        Winget-Install "OpenJS.NodeJS.LTS"
    }
    if (-not (Have pnpm)) {
        Write-Step "pnpm 설치 중..."
        npm install -g pnpm
        Refresh-Path
    }
}

# --- Python 3.10+ ---
function Ensure-Python {
    $py = $null
    foreach ($cmd in @("python", "python3")) {
        if (Have $cmd) { $py = $cmd; break }
    }
    if (-not $py) {
        Write-Step "Python 3.12 설치 중..."
        Winget-Install "Python.Python.3.12"
        $py = "python"
    }
    return $py
}

Ensure-Node
$Python = Ensure-Python

# --- 웹 스튜디오 의존성 ---
Write-Step "studio 의존성 설치 (pnpm install)..."
Push-Location (Join-Path $Root "studio")
if (Test-Path "pnpm-lock.yaml") { pnpm install --frozen-lockfile } else { pnpm install }
Pop-Location

# --- Python 엔진 가상환경 ---
Write-Step "engine 가상환경 및 의존성 설치..."
Push-Location (Join-Path $Root "engine")
if (-not (Test-Path ".venv")) { & $Python -m venv .venv }
& ".\.venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
Pop-Location

# --- AI CLI (선택) ---
Write-Step "AI CLI 설치 (선택)"
$choice = Read-Host "설치할 AI CLI를 선택하세요: [1] Claude Code (권장)  [2] Codex  [N] 건너뛰기"
switch ($choice) {
    "1" { npm i -g @anthropic-ai/claude-code@latest }
    "2" { npm i -g @openai/codex@latest }
    default { Write-Host "AI CLI 설치를 건너뜁니다. 웹 설정 화면에서 API 키만 입력해도 됩니다." }
}

Write-Host "`n설치 완료!" -ForegroundColor Green
Write-Host "실행:  cd `"$Root\studio`"; pnpm dev   (그 후 http://localhost:3020 접속)"
Write-Host "설정 화면(/settings)에서 Anthropic API 키를 저장하세요."
Write-Host "본인 테스트(라이선스 잠금 해제)는 run-dev.bat 더블클릭으로 바로 켤 수 있습니다." -ForegroundColor Cyan
