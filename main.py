import os
import io
import time
import secrets
from urllib.parse import urlencode
import httpx
import pandas as pd
from dotenv import load_dotenv

from fastapi import FastAPI, Request, Form, File, UploadFile, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

import database

import sys

# PyInstaller 실행 환경 대응
if getattr(sys, 'frozen', False):
    BASE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    EXEC_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    EXEC_DIR = BASE_DIR

# .env 환경변수 로드
load_dotenv(os.path.join(EXEC_DIR, ".env"))

CHZZK_CLIENT_ID = os.getenv("CHZZK_CLIENT_ID", "")
CHZZK_CLIENT_SECRET = os.getenv("CHZZK_CLIENT_SECRET", "")
CHZZK_REDIRECT_URI = os.getenv("CHZZK_REDIRECT_URI", "http://localhost:8000/auth/chzzk/callback")
ADMIN_CHANNEL_ID = os.getenv("ADMIN_CHANNEL_ID", "streamer_channel_123")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "streamer123!")
SECRET_KEY = os.getenv("SECRET_KEY", "chzzk_secret_key_2026")
ENABLE_MOCK_LOGIN = os.getenv("ENABLE_MOCK_LOGIN", "true").lower() == "true"

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB 파일 업로드 제한
ADMIN_CHANNEL_IDS = [x.strip() for x in ADMIN_CHANNEL_ID.split(",") if x.strip()]

app = FastAPI(title="Chzzk Coupon Pool Claim App")

# 보안 헤더 추가 미들웨어
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# 세션 미들웨어 추가
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# 정적 파일 및 템플릿 설정
static_dir = os.path.join(BASE_DIR, "static")
templates_dir = os.path.join(BASE_DIR, "templates")

app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)

@app.on_event("startup")
def on_startup():
    database.init_db()

@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    user = request.session.get("user")
    claim_result = None
    if user and "channel_id" in user:
        claim_result = database.claim_random_coupon(user["channel_id"], user.get("nickname", "시청자"))
        
    event_notice = database.get_event_notice()
        
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "user": user,
            "claim_result": claim_result,
            "event_notice": event_notice
        }
    )

# --- 치지직 OAuth 연동 ---
@app.get("/auth/chzzk/login")
async def chzzk_login(request: Request):
    if not CHZZK_CLIENT_ID or CHZZK_CLIENT_ID == "mock_client_id":
        return RedirectResponse(url="/auth/mock/login?channel_id=test_user_01&nickname=테스트유저01")
    
    state = secrets.token_urlsafe(16)
    request.session["oauth_state"] = state
    params = {
        "response_type": "code",
        "client_id": CHZZK_CLIENT_ID,
        "redirect_uri": CHZZK_REDIRECT_URI,
        "state": state
    }
    auth_url = f"https://nid.naver.com/oauth2.0/authorize?{urlencode(params)}"
    return RedirectResponse(url=auth_url)

@app.get("/auth/chzzk/callback")
async def chzzk_callback(request: Request, code: str = None, state: str = None):
    saved_state = request.session.get("oauth_state")
    if not state or not saved_state or state != saved_state:
        return RedirectResponse(url="/?error=csrf_validation_failed")
    
    if not code:
        return RedirectResponse(url="/?error=no_code")
    
    token_url = "https://nid.naver.com/oauth2.0/token"
    token_params = {
        "grant_type": "authorization_code",
        "client_id": CHZZK_CLIENT_ID,
        "client_secret": CHZZK_CLIENT_SECRET,
        "code": code,
        "state": state
    }
    
    try:
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(token_url, data=token_params)
            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            
            if not access_token:
                return RedirectResponse(url="/?error=token_failed")
            
            # 1차 시도: 네이버아이디로그인 프로필 API (developers.naver.com 앱)
            profile_url = "https://openapi.naver.com/v1/nid/me"
            headers = {"Authorization": f"Bearer {access_token}"}
            profile_resp = await client.get(profile_url, headers=headers)
            profile_data = profile_resp.json()
            
            user_info = profile_data.get("response", profile_data.get("content", profile_data))
            channel_id = str(user_info.get("id", user_info.get("channelId", "")))
            nickname = user_info.get("nickname", user_info.get("name", "치지직시청자"))
            
            # 2차 시도: 치지직 전용 오픈 API 프로필 (chzzk.naver.com 앱)
            if not channel_id:
                chzzk_profile_url = "https://openapi.chzzk.naver.com/open/v1/users/me"
                chzzk_resp = await client.get(chzzk_profile_url, headers=headers)
                chzzk_data = chzzk_resp.json()
                user_info = chzzk_data.get("content", chzzk_data)
                channel_id = str(user_info.get("channelId", user_info.get("id", "")))
                nickname = user_info.get("nickname", "치지직시청자")
            
            if not channel_id:
                print(f"Profile Fetch Failed. Data: {profile_data}")
                return RedirectResponse(url="/?error=profile_failed")
            
            request.session["user"] = {
                "channel_id": channel_id,
                "nickname": nickname
            }
            
            if channel_id in ADMIN_CHANNEL_IDS:
                request.session["is_admin"] = True
                
    except Exception as e:
        print(f"OAuth Callback Error: {e}")
        return RedirectResponse(url="/?error=exception")
    
    return RedirectResponse(url="/")

@app.get("/auth/mock/login")
async def mock_login(request: Request, channel_id: str = "test_user_01", nickname: str = "시뮬레이션유저"):
    if not ENABLE_MOCK_LOGIN:
        return RedirectResponse(url="/?error=mock_login_disabled")
        
    request.session["user"] = {
        "channel_id": channel_id,
        "nickname": nickname
    }
    if channel_id in ADMIN_CHANNEL_IDS:
        request.session["is_admin"] = True
    return RedirectResponse(url="/")

@app.get("/auth/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")

# --- 진행자(Host/Admin) 관리자 기능 ---
@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, msg: str = None, error_msg: str = None, search: str = None, winner_search: str = None):
    is_admin = request.session.get("is_admin", False)
    coupons = database.get_all_coupons(search_query=search) if is_admin else []
    stats = database.get_coupon_pool_stats() if is_admin else {}
    allowed_winners = database.get_allowed_winners(search_query=winner_search) if is_admin else []
    allow_all = database.is_allow_all_users() if is_admin else False
    event_notice = database.get_event_notice() if is_admin else ""
    
    return templates.TemplateResponse(
        request,
        "admin.html",
        {
            "is_admin": is_admin,
            "coupons": coupons,
            "stats": stats,
            "allowed_winners": allowed_winners,
            "allow_all": allow_all,
            "event_notice": event_notice,
            "search_query": search or "",
            "winner_search_query": winner_search or "",
            "chzzk_client_id": CHZZK_CLIENT_ID,
            "chzzk_client_secret": CHZZK_CLIENT_SECRET,
            "chzzk_redirect_uri": CHZZK_REDIRECT_URI,
            "enable_mock_login": ENABLE_MOCK_LOGIN,
            "msg": msg,
            "error_msg": error_msg
        }
    )

@app.post("/admin/login")
async def admin_login(request: Request, password: str = Form(...)):
    current_pass = database.get_admin_password()
    if password == current_pass:
        request.session["is_admin"] = True
        return RedirectResponse(url="/admin", status_code=303)
    
    # 비밀번호 실패 시 지연 처리 (Brute-Force 방어)
    time.sleep(1.0)
    return templates.TemplateResponse(
        request,
        "admin.html",
        {
            "is_admin": False,
            "coupons": [],
            "stats": {},
            "allowed_winners": [],
            "allow_all": False,
            "event_notice": "",
            "search_query": "",
            "error_msg": "관리자 비밀번호가 올바르지 않습니다."
        }
    )

@app.get("/admin/logout")
async def admin_logout(request: Request):
    request.session["is_admin"] = False
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/change-password")
async def admin_change_password(request: Request, new_password: str = Form(...)):
    if not request.session.get("is_admin"):
        return RedirectResponse(url="/admin", status_code=303)
    if len(new_password.strip()) < 4:
        return RedirectResponse(url="/admin?error_msg=비밀번호는 최소 4자리 이상이어야 합니다.", status_code=303)
    database.set_admin_password(new_password)
    
    global ADMIN_PASSWORD
    ADMIN_PASSWORD = new_password
    env_path = os.path.join(EXEC_DIR, ".env")
    env_content = f"""# 치지직 Open API Client Credentials
CHZZK_CLIENT_ID={CHZZK_CLIENT_ID}
CHZZK_CLIENT_SECRET={CHZZK_CLIENT_SECRET}
CHZZK_REDIRECT_URI={CHZZK_REDIRECT_URI}

# 시뮬레이션(Mock) 테스트 로그인 활성화 여부
ENABLE_MOCK_LOGIN={'true' if ENABLE_MOCK_LOGIN else 'false'}

# 관리자(진행자) 설정
ADMIN_CHANNEL_ID={ADMIN_CHANNEL_ID}
ADMIN_PASSWORD={ADMIN_PASSWORD}

# 세션 비밀키
SECRET_KEY={SECRET_KEY}
"""
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(env_content)
        
    return RedirectResponse(url="/admin?msg=관리자 비밀번호가 성공적으로 변경되었습니다.", status_code=303)

@app.post("/admin/update-env")
async def admin_update_env(
    request: Request,
    client_id: str = Form(""),
    client_secret: str = Form(""),
    redirect_uri: str = Form(""),
    enable_mock_login: bool = Form(False)
):
    if not request.session.get("is_admin"):
        return RedirectResponse(url="/admin", status_code=303)
        
    global CHZZK_CLIENT_ID, CHZZK_CLIENT_SECRET, CHZZK_REDIRECT_URI, ENABLE_MOCK_LOGIN
    
    CHZZK_CLIENT_ID = client_id.strip()
    CHZZK_CLIENT_SECRET = client_secret.strip()
    CHZZK_REDIRECT_URI = redirect_uri.strip()
    ENABLE_MOCK_LOGIN = enable_mock_login
    
    env_path = os.path.join(EXEC_DIR, ".env")
    env_content = f"""# 치지직 Open API Client Credentials
CHZZK_CLIENT_ID={CHZZK_CLIENT_ID}
CHZZK_CLIENT_SECRET={CHZZK_CLIENT_SECRET}
CHZZK_REDIRECT_URI={CHZZK_REDIRECT_URI}

# 시뮬레이션(Mock) 테스트 로그인 활성화 여부
ENABLE_MOCK_LOGIN={'true' if ENABLE_MOCK_LOGIN else 'false'}

# 관리자(진행자) 설정
ADMIN_CHANNEL_ID={ADMIN_CHANNEL_ID}
ADMIN_PASSWORD={ADMIN_PASSWORD}

# 세션 비밀키
SECRET_KEY={SECRET_KEY}
"""
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(env_content)
        
    return RedirectResponse(url="/admin?msg=네이버 치지직 API 키 및 접속 설정이 성공적으로 저장되었습니다!", status_code=303)

@app.post("/admin/notice")
async def admin_update_notice(request: Request, event_notice: str = Form(...)):
    if not request.session.get("is_admin"):
        return RedirectResponse(url="/admin", status_code=303)
    database.set_event_notice(event_notice)
    return RedirectResponse(url="/admin?msg=시청자 페이지 이벤트 공지 문구가 갱신되었습니다.", status_code=303)


@app.post("/admin/config/allow-all")
async def admin_config_allow_all(request: Request, allow_all: bool = Form(False)):
    if not request.session.get("is_admin"):
        return RedirectResponse(url="/admin", status_code=303)
    database.set_allow_all_users(allow_all)
    status_str = "모든 치지직 유저 수령 허용 모드" if allow_all else "지정 당첨자 전용 모드"
    return RedirectResponse(url=f"/admin?msg=수령 설정이 변경되었습니다: [{status_str}]", status_code=303)

@app.post("/admin/add-coupon")
async def admin_add_coupon(request: Request, coupon_code: str = Form(...)):
    if not request.session.get("is_admin"):
        return RedirectResponse(url="/admin", status_code=303)
    database.add_coupon_to_pool(coupon_code)
    return RedirectResponse(url="/admin?msg=쿠폰 코드가 쿠폰 풀에 추가되었습니다.", status_code=303)

@app.post("/admin/upload-coupons-csv")
async def admin_upload_coupons_csv(request: Request, file: UploadFile = File(...)):
    if not request.session.get("is_admin"):
        return RedirectResponse(url="/admin", status_code=303)
    try:
        contents = await file.read()
        if len(contents) > MAX_FILE_SIZE:
            return RedirectResponse(url="/admin?error_msg=CSV 파일 크기가 제한(5MB)을 초과했습니다.", status_code=303)
            
        df = database.read_csv_robustly(contents)
        if len(df) > 10000:
            return RedirectResponse(url="/admin?error_msg=한 번에 최대 10,000행까지 업로드 가능합니다.", status_code=303)
            
        count = database.import_coupons_csv(df)
        return RedirectResponse(url=f"/admin?msg=총 {count}개의 선물 쿠폰 코드가 쿠폰 풀에 등록되었습니다.", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/admin?error_msg=쿠폰 CSV 업로드 실패: {str(e)}", status_code=303)

@app.post("/admin/add-winner")
async def admin_add_winner(request: Request, channel_id: str = Form(...), nickname: str = Form("치지직시청자")):
    if not request.session.get("is_admin"):
        return RedirectResponse(url="/admin", status_code=303)
    database.add_allowed_winner(channel_id, nickname)
    return RedirectResponse(url="/admin?msg=당첨 대상자가 명단에 추가되었습니다.", status_code=303)

@app.post("/admin/upload-winners-csv")
async def admin_upload_winners_csv(request: Request, file: UploadFile = File(...)):
    if not request.session.get("is_admin"):
        return RedirectResponse(url="/admin", status_code=303)
    try:
        contents = await file.read()
        if len(contents) > MAX_FILE_SIZE:
            return RedirectResponse(url="/admin?error_msg=CSV 파일 크기가 제한(5MB)을 초과했습니다.", status_code=303)
            
        df = database.read_csv_robustly(contents)
        if len(df) > 10000:
            return RedirectResponse(url="/admin?error_msg=한 번에 최대 10,000행까지 업로드 가능합니다.", status_code=303)
            
        count = database.import_allowed_winners_csv(df)
        return RedirectResponse(url=f"/admin?msg=총 {count}명의 당첨 대상자가 등록되었습니다.", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/admin?error_msg=당첨자 CSV 업로드 실패: {str(e)}", status_code=303)

@app.post("/admin/delete-winner")
async def admin_delete_winner(request: Request, channel_id: str = Form(...)):
    if not request.session.get("is_admin"):
        return RedirectResponse(url="/admin", status_code=303)
    database.delete_allowed_winner(channel_id)
    return RedirectResponse(url="/admin?msg=당첨 대상자가 삭제되었습니다.", status_code=303)

@app.post("/admin/clear-winners")
async def admin_clear_winners(request: Request):
    if not request.session.get("is_admin"):
        return RedirectResponse(url="/admin", status_code=303)
    count = database.clear_all_allowed_winners()
    return RedirectResponse(url=f"/admin?msg=당첨 대상자 명단 {count}명이 모두 삭제되었습니다.", status_code=303)

@app.get("/admin/export-winners-csv")
async def admin_export_winners_csv(request: Request):
    if not request.session.get("is_admin"):
        return RedirectResponse(url="/admin", status_code=303)
    winners = database.get_allowed_winners()
    df = pd.DataFrame(winners)
    output = io.StringIO()
    df.to_csv(output, index=False, encoding='utf-8-sig')
    
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=allowed_winners_export.csv"}
    )

@app.post("/admin/reset-coupon")
async def admin_reset_coupon(request: Request, coupon_id: int = Form(...)):
    if not request.session.get("is_admin"):
        return RedirectResponse(url="/admin", status_code=303)
    database.reset_coupon_assignment(coupon_id)
    return RedirectResponse(url="/admin?msg=쿠폰 발급 상태가 리셋되어 다시 사용 가능해졌습니다.", status_code=303)

@app.post("/admin/delete-coupon")
async def admin_delete_coupon(request: Request, coupon_id: int = Form(...)):
    if not request.session.get("is_admin"):
        return RedirectResponse(url="/admin", status_code=303)
    database.delete_coupon_from_pool(coupon_id)
    return RedirectResponse(url="/admin?msg=쿠폰이 삭제되었습니다.", status_code=303)

@app.post("/admin/clear-coupons")
async def admin_clear_coupons(request: Request):
    if not request.session.get("is_admin"):
        return RedirectResponse(url="/admin", status_code=303)
    count = database.clear_all_coupons()
    return RedirectResponse(url=f"/admin?msg=쿠폰 풀의 모든 선물 쿠폰 {count}개가 일괄 삭제되었습니다.", status_code=303)

@app.get("/admin/export-coupons-csv")
async def admin_export_coupons_csv(request: Request):
    if not request.session.get("is_admin"):
        return RedirectResponse(url="/admin", status_code=303)
    coupons = database.get_all_coupons()
    df = pd.DataFrame(coupons)
    output = io.StringIO()
    df.to_csv(output, index=False)
    
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=coupon_pool_export.csv"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
