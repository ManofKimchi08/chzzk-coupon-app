import os
import sys
import webbrowser
import threading
import time
import uvicorn
from main import app

def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://localhost:8000")

if __name__ == "__main__":
    print("=" * 60)
    print("  🎉 치지직 1회성 쿠폰 이벤트 서버 실행 중...")
    print("  접속 주소: http://localhost:8000")
    print("  진행자 대시보드: http://localhost:8000/admin")
    print("=" * 60)
    
    # 자동으로 브라우저 열기
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Uvicorn 서버 시작
    uvicorn.run(app, host="0.0.0.0", port=8000)
