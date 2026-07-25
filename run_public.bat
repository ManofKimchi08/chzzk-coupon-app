@echo off
chcp 65001 > nul
echo =================================================================
echo 🎁 치지직 쿠폰 이벤트 서버 및 외부 공개 주소 생성기
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
echo 2. 외부 시청자들이 접속할 수 있는 전용 무설치 URL(https://...)을 생성합니다.
echo.
echo -----------------------------------------------------------------
echo 💡 [필독] 잠시 후 아래 화면에 출력되는 https://xxxx.lhr.life 주소를 복사하여
echo    1) 네이버 개발자 센터 Callback URL 및 서비스 URL에 등록하고
echo    2) 시청자들에게 이벤트 수령 주소로 공유해 주세요!
echo -----------------------------------------------------------------
echo.

ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -R 80:localhost:8000 nokey@localhost.run
pause
