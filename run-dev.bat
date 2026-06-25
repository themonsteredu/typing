@echo off
REM Exam Studio - 소유자/개발 테스트 런처 (더블클릭용)
REM 라이선스 잠금을 해제(EXAM_STUDIO_DEV=1)하고 개발 서버를 기동합니다.
REM 고객 배포본에서는 사용하지 마세요.
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0run-dev.ps1"
pause
