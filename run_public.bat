@echo off
chcp 65001 > nul
cls
echo =================================================================
echo  치지직 쿠폰 이벤트 서버 외부 공개 주소 생성기
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
timeout /t 2 > nul

echo.
echo 2. 외부 접속용 무설치 전용 주소를 생성 중입니다...
echo.
echo -----------------------------------------------------------------
echo [필독] 잠시 후 화면에 나오는 https://xxxx.lhr.life 주소를 복사하세요
echo -----------------------------------------------------------------
echo.

ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -R 80:localhost:8000 nokey@localhost.run
pause
