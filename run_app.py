import os
import sys
import webbrowser
import threading
import time
import uvicorn
from main import app
import tunnel_manager


def start_tunnel():
    if getattr(sys, 'frozen', False):
        exec_dir = os.path.dirname(sys.executable)
    else:
        exec_dir = os.path.dirname(os.path.abspath(__file__))

    token = os.getenv("CLOUDFLARE_TUNNEL_TOKEN", "").strip()
    if not token:
        env_file = os.path.join(exec_dir, ".env")
        if os.path.exists(env_file):
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("CLOUDFLARE_TUNNEL_TOKEN="):
                        token = line.split("=", 1)[1].strip()
                        break

    tunnel_manager.start_or_restart_tunnel(exec_dir, token)


def open_browser():
    time.sleep(1.8)
    webbrowser.open("http://localhost:8000/admin")


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))

    print("=" * 60)
    print("  🎉 치지직 1회성 쿠폰 이벤트 서버 원클릭 가동 중...")
    print(f"  접속 주소: http://localhost:{port}")
    print(f"  진행자 대시보드: http://localhost:{port}/admin")
    print("=" * 60)

    # 자동으로 Cloudflare 터널 및 브라우저 열기
    threading.Thread(target=start_tunnel, daemon=True).start()
    threading.Thread(target=open_browser, daemon=True).start()

    # Uvicorn 서버 시작 (로컬 루프백 전용 바인딩으로 내부망 직접 접근 차단)
    uvicorn.run(app, host=host, port=port)
