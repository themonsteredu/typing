#!/usr/bin/env bash
# Exam Studio - macOS/Linux 실행 런처
# 의존성을 설치(최초 1회)하고 개발 서버를 http://localhost:3020 에 기동합니다.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

step() { printf "\n==> %s\n" "$1"; }

# --- Node ---
if ! command -v node >/dev/null 2>&1; then
  echo "Node.js 22+ 가 필요합니다. https://nodejs.org 에서 설치하세요." >&2
  exit 1
fi

# pnpm 우선, 없으면 npm
if command -v pnpm >/dev/null 2>&1; then
  PKG="pnpm"
else
  PKG="npm"
fi

# --- Python ---
PY="python3"
command -v "$PY" >/dev/null 2>&1 || PY="python"
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "Python 3.10+ 가 필요합니다." >&2
  exit 1
fi

# --- studio 의존성 ---
if [ ! -d "studio/node_modules" ]; then
  step "studio 의존성 설치 ($PKG install)"
  (cd studio && $PKG install)
fi

# --- engine 가상환경 ---
if [ ! -d "engine/.venv" ]; then
  step "engine 가상환경 및 의존성 설치"
  (cd engine && "$PY" -m venv .venv && ./.venv/bin/python -m pip install --quiet --upgrade pip \
    && ./.venv/bin/python -m pip install --quiet -r requirements.txt)
fi

step "개발 서버 기동: http://localhost:3020"
cd studio
exec $PKG run dev
