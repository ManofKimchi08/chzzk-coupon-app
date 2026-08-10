import os
import sys
import webbrowser
import threading
import time
import subprocess
import uvicorn
from main import app

def start_tunnel():
    if getattr(sys, 'frozen', False):
        exec_dir = os.path.dirname(sys.executable)
    else:
        exec_dir = os.path.dirname(os.path.abspath(__file__))
    
    cloudflared_path = os.path.join(exec_dir, "cloudflared.exe")
    if not os.path.exists(cloudflared_path):
        parent_cloudflared = os.path.join(os.path.dirname(exec_dir), "cloudflared.exe")
        if os.path.exists(parent_cloudflared):
            cloudflared_path = parent_cloudflared

    if os.path.exists(cloudflared_path):
        try:
            token = os.getenv("CLOUDFLARE_TUNNEL_TOKEN", "").strip()
            if not token:
                env_file = os.path.join(exec_dir, ".env")
                if os.path.exists(env_file):
                    with open(env_file, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.startswith("CLOUDFLARE_TUNNEL_TOKEN="):
                                token = line.split("=", 1)[1].strip()
                                break
            
            if token:
                print("🚀 Cloudflare [고정 터널 (Named Tunnel)]을 자동으로 시작합니다...")
                cmd = [cloudflared_path, "tunnel", "run", "--token", token]
            else:
                print("🚀 Cloudflare [임시 터널 (Quick Tunnel)]을 자동으로 시작합니다...")
                cmd = [cloudflared_path, "tunnel", "--url", "http://localhost:8000", "--metrics", "127.0.0.1:20241"]

            creation_flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation_flags
            )
        except Exception as e:
            print(f"터널 자동 실행 실패: {e}")

def open_browser():
    time.sleep(1.8)
    webbrowser.open("http://localhost:8000/admin")

if __name__ == "__main__":
    print("=" * 60)
    print("  🎉 치지직 1회성 쿠폰 이벤트 서버 원클릭 가동 중...")
    print("  접속 주소: http://localhost:8000")
    print("  진행자 대시보드: http://localhost:8000/admin")
    print("=" * 60)
    
    # 자동으로 Cloudflare 터널 및 브라우저 열기
    threading.Thread(target=start_tunnel, daemon=True).start()
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Uvicorn 서버 시작
    uvicorn.run(app, host="0.0.0.0", port=8000)
