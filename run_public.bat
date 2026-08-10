@echo off
chcp 65001 > nul
cls
echo =================================================================
echo  🎁 치지직 쿠폰 이벤트 - Cloudflare 고속 외부 공개 실행기
echo =================================================================
echo.

echo 1. 서버 실행 확인 중...
if exist "ChzzkCouponServer.exe" (
    start "" "ChzzkCouponServer.exe"
) else if exist "dist\ChzzkCouponServer\ChzzkCouponServer.exe" (
    start "" "dist\ChzzkCouponServer\ChzzkCouponServer.exe"
) else (
    start "" python run_app.py
)
timeout /t 3 > nul

echo.
echo 2. Cloudflare 터널 프로그램 확인 중...
if not exist "cloudflared.exe" (
    if exist "..\cloudflared.exe" (
        copy "..\cloudflared.exe" "cloudflared.exe" > nul
    ) else (
        echo [안내] 최초 1회 Cloudflare 터널 모듈을 구성합니다...
        python -c "import urllib.request; urllib.request.urlretrieve('https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe', 'cloudflared.exe')"
    )
)

echo.
echo 3. 외부 접속용 HTTPS 전용 주소(trycloudflare.com)를 생성합니다...
echo -----------------------------------------------------------------
echo 💡 웹 브라우저 관리자 대시보드(http://localhost:8000/admin)에 접속하시면
echo    생성된 외부 접속 주소(https://...)를 1초 만에 확인하고 복사할 수 있습니다!
echo -----------------------------------------------------------------
echo.

cloudflared.exe tunnel --url http://localhost:8000 --metrics 127.0.0.1:20241
pause
