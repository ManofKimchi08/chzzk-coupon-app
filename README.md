# 🎁 치지직(CHZZK) 1회성 무작위 쿠폰 매핑 수령 웹 애플리케이션

![Chzzk Event](https://img.shields.io/badge/Chzzk-00FFA3?style=for-the-badge&logo=naver&logoColor=000)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)

치지직(CHZZK) 스트리머 이벤트를 위한 **시청자 본인 인증 기반 1회성 난수 쿠폰 코드 무작위 수령 및 진행자 전용 대시보드 웹 플랫폼**입니다.

---

## ✨ 핵심 기능

- **🔒 치지직 OAuth 2.0 본인 인증**: 사용자의 고유 `channelId`를 오픈 API(`/open/v1/users/me`)로 안전하게 검증
- **🎲 무작위(Random) 1인 1회 쿠폰 자동 할당**: 쿠폰 풀(Pool)에서 남아있는 난수 코드를 1개씩 무작위 추첨 발급
- **🛡️ 중복 수령 및 CSRF 차단**: 동일 채널 ID 1회 수령 제한 및 암호학적 State 토큰 검증
- **🎙️ 진행자(스트리머) 전용 관리자 대시보드 (`/admin`)**:
  - 쿠폰 코드 및 당첨 대상자 명단 웹 폼 또는 CSV 파일로 대량 일괄 등록
  - 수령 대상자 제한 범위 온/오프 스위치 (지정 당첨자 전용 vs 전체 로그인 유저 허용)
  - 실시간 수령 현황 통계 (`총 쿠폰 수`, `발급 수`, `남은 수량`) 및 수령 상태 리셋/CSV 다운로드
- **🚀 포터블 무설치 실행 지원**: PyInstaller로 빌드된 `.exe` 실행 파일로 파이썬 미설치 환경에서도 클릭 한 번으로 가동

---

## 🛠️ 기술 스택

- **Backend**: Python 3.13+, FastAPI, Uvicorn, Starlette Session Middleware
- **Database**: SQLite3 (Atomic Transaction `BEGIN IMMEDIATE` 동시성 처리)
- **Data Processing**: Pandas
- **Frontend**: HTML5, Jinja2 Template, Vanilla CSS (치지직 네온 다크 브랜드 테마)
- **Deployment & Packaging**: PyInstaller, Localtunnel

---

## 🚀 시작하기

### 1. 환경 변수 세팅 (`.env`)

네이버 개발자 센터에서 발급받은 API 키를 `.env` 파일에 작성합니다. (`.env.example` 참고)

```env
CHZZK_CLIENT_ID=your_chzzk_client_id
CHZZK_CLIENT_SECRET=your_chzzk_client_secret
CHZZK_REDIRECT_URI=http://localhost:8000/auth/chzzk/callback

ENABLE_MOCK_LOGIN=true

ADMIN_CHANNEL_ID=your_chzzk_channel_id
ADMIN_PASSWORD=your_admin_password
SECRET_KEY=your_secret_session_key
```

### 2. 실행 방법

#### 방법 A) 개발 환경 (Python)
```bash
git clone https://github.com/ManofKimchi08/chzzk-coupon-app.git
cd chzzk-coupon-app
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

#### 방법 B) 무설치 실행 (포터블 실행 파일)
`dist/ChzzkCouponServer/ChzzkCouponServer.exe` 파일 또는 `run_server.bat`을 더블클릭합니다.

---

## 📖 접속 주소

- **시청자 쿠폰 수령 페이지**: `http://localhost:8000`
- **진행자 관리자 대시보드**: `http://localhost:8000/admin`

---

## 📄 라이선스
MIT License
