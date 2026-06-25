# Exam Studio - 소유자/개발 테스트 런처 (Windows)
#
# ⚠️ 이 런처는 라이선스 잠금을 해제(EXAM_STUDIO_DEV=1)합니다. 본인이 직접
#    테스트할 때만 쓰세요. 고객에게 주는 배포본에서는 절대 쓰지 마세요.
#    (고객은 install.ps1 안내대로 라이선스 키를 활성화해서 사용합니다.)
#
# 하는 일: 의존성(최초 1회) 설치 -> 개발 서버를 http://localhost:3020 에 기동 -> 브라우저 자동 오픈

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Have($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

Write-Host "============================================================" -ForegroundColor Yellow
Write-Host " 개발/소유자 테스트 전용 런처 — 라이선스 잠금을 해제합니다." -ForegroundColor Yellow
Write-Host " 고객 배포본에서는 사용하지 마세요." -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Yellow

# 라이선스 게이트 우회 (studio/lib/license.ts 가 이 값을 확인)
$env:EXAM_STUDIO_DEV = "1"

# --- 최초 1회 의존성 설치 (studio/node_modules 또는 engine/.venv 가 없을 때) ---
$needInstall = -not (Test-Path (Join-Path $Root "studio\node_modules")) -or `
               -not (Test-Path (Join-Path $Root "engine\.venv"))
if ($needInstall) {
    $install = Join-Path $Root "install.ps1"
    if (Test-Path $install) {
        Write-Step "의존성이 없어 install.ps1 로 설치합니다 (최초 1회, 수 분 소요)"
        & powershell -ExecutionPolicy Bypass -File $install
    } else {
        throw "install.ps1 을 찾을 수 없습니다: $install"
    }
}

# --- 패키지 매니저 선택 (pnpm 우선, 없으면 npm) ---
$pkg = if (Have pnpm) { "pnpm" } else { "npm" }

# --- 브라우저 자동 오픈 (서버 뜰 시간을 잠깐 준 뒤) ---
Start-Job -ScriptBlock {
    Start-Sleep -Seconds 6
    Start-Process "http://localhost:3020"
} | Out-Null

Write-Step "개발 서버 기동: http://localhost:3020  (종료: 이 창에서 Ctrl+C)"
Push-Location (Join-Path $Root "studio")
try {
    & $pkg run dev
} finally {
    Pop-Location
}
