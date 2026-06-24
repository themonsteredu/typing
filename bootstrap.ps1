# Exam Studio - Windows bootstrap
# 사용법:  irm https://raw.githubusercontent.com/themonsteredu/typing/main/bootstrap.ps1 | iex
#
# Git 확인/설치 -> 저장소 clone 또는 update -> install.ps1 실행

$ErrorActionPreference = "Stop"

$RepoUrl = "https://github.com/themonsteredu/typing.git"
$Dest    = Join-Path $env:USERPROFILE "exam-studio"

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

# --- Git 확인, 없으면 winget으로 설치 ---
function Ensure-Git {
    if (Get-Command git -ErrorAction SilentlyContinue) { return }
    Write-Step "Git이 없어 winget으로 설치합니다..."
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "winget을 찾을 수 없습니다. https://git-scm.com 에서 Git을 직접 설치한 뒤 다시 실행하세요."
    }
    winget install --id Git.Git -e --source winget --accept-source-agreements --accept-package-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path", "User")
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw "Git 설치 후에도 git을 찾을 수 없습니다. 새 PowerShell 창에서 다시 실행하세요."
    }
}

# PowerShell 5.1은 git의 stderr 출력을 오류로 취급하므로 일시적으로 완화
function Invoke-Git {
    param([Parameter(ValueFromRemainingArguments = $true)] $Args)
    $old = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & git @Args
        if ($LASTEXITCODE -ne 0) { throw "git $($Args -join ' ') 실패 (exit $LASTEXITCODE)" }
    } finally {
        $ErrorActionPreference = $old
    }
}

Ensure-Git

if (Test-Path (Join-Path $Dest ".git")) {
    Write-Step "기존 저장소를 origin/main으로 업데이트합니다: $Dest"
    Invoke-Git -C $Dest fetch --quiet origin main
    # pull --ff-only 대신 fetch + reset --hard: 강제 푸시/오래된 코드도 안전하게 동기화.
    # 추적되지 않는 파일(.env, .venv, node_modules)은 보존됩니다.
    Invoke-Git -C $Dest reset --hard --quiet origin/main
} else {
    Write-Step "저장소를 클론합니다: $Dest"
    Invoke-Git clone --quiet $RepoUrl $Dest
}

# --- install.ps1로 위임 ---
$Install = Join-Path $Dest "install.ps1"
if (-not (Test-Path $Install)) { throw "install.ps1을 찾을 수 없습니다: $Install" }

Write-Step "설치 스크립트를 실행합니다: install.ps1"
& powershell -ExecutionPolicy Bypass -File $Install
