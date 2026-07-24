@echo off
chcp 65001 >nul
title 치지직 쿠폰 이벤트 서버
echo ==========================================================
echo   🎉 치지직 1회성 무작위 쿠폰 수령 서버를 시작합니다...
echo   웹 접속 주소: http://localhost:8000
echo   진행자 대시보드: http://localhost:8000/admin
echo ==========================================================
echo.
timeout /t 2 /nobreak >nul
start http://localhost:8000
"%~dp0venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8000
pause
