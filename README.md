# 🎁 치지직(CHZZK) 1회성 무작위 쿠폰 수령 플랫폼 (인수인계 & 운영 가이드)

![Chzzk Event](https://img.shields.io/badge/Chzzk-00FFA3?style=for-the-badge&logo=naver&logoColor=000)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)

치지직(CHZZK) 스트리머 이벤트를 위한 **시청자 본인 인증 기반 1회성 선물 쿠폰 무작위 수령 및 진행자 관리 웹 플랫폼**입니다.  
본 리포지토리 및 프로그램은 타 스트리머, 매니저, 운영진에게 즉시 인수인계하여 운영할 수 있도록 제작되었습니다.

---

## ✨ 핵심 기능 요약

- **🔒 치지직 OAuth 2.0 본인 인증**: 시청자의 고유 `channelId`를 오픈 API로 검증하여 중복 수령 완벽 차단
- **🎲 무작위(Random) 쿠폰 자동 할당**: 쿠폰 풀(Pool)에서 남아있는 선물 코드를 1개씩 무작위 자동 발급
- **🎙️ 진행자 전용 관리자 대시보드 (`/admin`)**:
  - **🔑 웹 UI 상에서 네이버 치지직 API 키 직접 입력 & 실시간 동기화 (메모장 편집 불필요)**
  - 쿠폰 코드 및 당첨자 명단 대량 CSV 업로드 (UTF-8 BOM/CP949/EUC-KR 및 순번 제외 스마트 컬럼 자동 감지)
  - 등록된 당첨자 명단 현황 및 쿠폰 수령 상태 실시간 아코디언 UI 조회/검색
  - 쿠폰 및 당첨자 명단 전체 일괄 삭제 (`🗑️ 전체 쿠폰 삭제`, `🗑️ 전체 명단 삭제`)
  - 쿠폰 풀 및 당첨자 명단 CSV 내보내기 다운로드
  - 실시간 수령 내역 검색, 수령 상태 초기화(리셋) 및 공지 문구 편집
- **🚀 무설치 포터블 가동 지원**: 파이썬이 설치되어 있지 않은 컴에서도 `.exe` 실행 파일 클릭으로 바로 구동

---

## 📂 폴더 및 파일 구조

```
chzzk-coupon-app/
├── dist/ChzzkCouponServer/           # 🚀 [인수인계용] 무설치 포터블 패키지 폴더
│   ├── ChzzkCouponServer.exe        # 실행 파일 (더블클릭 시 서버 구동 + 브라우저 자동 오픈)
│   ├── .env                         # ⚙️ API 키 및 비밀번호 설정 파일 (웹 UI 또는 메모장으로 수정)
│   └── HANDOVER_MANUAL.md           # 상세 운영 매뉴얼 문서
├── database.py                      # SQLite 데이터베이스 및 무작위 쿠폰 할당 트랜잭션 로직
├── main.py                          # FastAPI 백엔드 라우터 및 OAuth 본인인증
├── run_server.bat                   # 개발 환경 배치 실행 파일
├── templates/                       # HTML 웹 UI 템플릿 (Jinja2)
└── static/                          # CSS 스타일시트 및 캐릭터 이미지 자산
```

---

## 🔑 필수 환경설정 (웹 UI 또는 `.env` 세팅법)

인수인계받은 담당자는 서버 실행 후 관리자 대시보드(`http://localhost:8000/admin`)의 **`🔑 네이버 치지직 API 키 및 서버 설정`** 카드에서 직접 입력 및 저장하거나, **`.env`** 파일을 메모장으로 열어 설정할 수 있습니다.

### 1단계: 네이버 치지직 개발자 센터 API 등록
1. [네이버 개발자 센터(Naver Developers)](https://developers.naver.com/) 접속 ➔ 로그인 ➔ **[Application] ➔ [애플리케이션 등록]**
2. **애플리케이션 이름**: `치지직 쿠폰 이벤트` (자유롭게 입력)
3. **사용 API**: `네이버 로그인` 선택 ➔ **별명** 항목 **필수** 선택 *(이용자 식별자는 기본 자동 제공)*
4. **로그인 오픈 API 서비스 환경**: **`WEB 설정`** 선택
   - **서비스 URL**: `http://localhost:8000`
   - **Callback URL**: `http://localhost:8000/auth/chzzk/callback` *(⚠️ 주소 오탈자 주의)*
5. 등록 완료 후 생성된 **Client ID** 및 **Client Secret** 값을 복사합니다.

### 2단계: API 키 등록 (웹 대시보드 UI 또는 `.env` 파일)
서버 실행 후 `http://localhost:8000/admin` 접속 ➔ **`🔑 네이버 치지직 API 키 및 서버 설정`** 카드에 복사한 키 값을 입력하고 **[💾 API 설정 저장]** 버튼을 클릭하면 즉시 반영됩니다. (또는 `.env` 파일 메모장 편집 가능)

```env
# 1. 네이버 개발자 센터에서 발급받은 실제 API 키값
CHZZK_CLIENT_ID=발급받은_Client_ID_입력
CHZZK_CLIENT_SECRET=발급받은_Client_Secret_입력
CHZZK_REDIRECT_URI=http://localhost:8000/auth/chzzk/callback

# 2. 테스트 로그인 허용 여부 (실제 운영 시에는 false 권장)
ENABLE_MOCK_LOGIN=true

# 3. 스트리머 및 매니저들의 치지직 채널 ID (쉼표로 구분하여 여러 명 지정 가능)
# 등록된 계정으로 로그인 시 자동으로 관리자 대시보드 접근 권한이 부여됩니다.
ADMIN_CHANNEL_ID=스트리머_채널_ID, 매니저1_채널_ID

# 4. 진행자 관리자 페이지 (/admin) 접속 비밀번호
ADMIN_PASSWORD=streamer123!

# 5. 세션 암호화 보안키 (자유롭게 변경 가능)
SECRET_KEY=chzzk_coupon_secret_key_2026
```

---

## 🚀 프로그램 실행 방법

### 방법 A: 파이썬 미설치 환경 (무설치 포터블 `.exe` - 권장 ⭐)
1. `dist/ChzzkCouponServer` 폴더로 이동합니다.
2. **`ChzzkCouponServer.exe`** 파일을 더블클릭합니다.
3. 까만 터미널 창이 뜨면서 서버가 구동되고, **자동으로 웹 브라우저(`http://localhost:8000`)가 열립니다.**

### 방법 B: 파이썬 개발 환경 (Source Code)
```bash
git clone https://github.com/ManofKimchi08/chzzk-coupon-app.git
cd chzzk-coupon-app
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🕹️ 접속 주소 및 운영 가이드

- **시청자 쿠폰 수령 페이지**: `http://localhost:8000`
- **진행자 관리자 대시보드**: `http://localhost:8000/admin`

### 관리자 주요 작동 순서
1. **관리자 로그인**: `/admin` 접속 후 `.env`에 지정한 비밀번호(`ADMIN_PASSWORD`) 입력 또는 스트리머 계정으로 로그인.
2. **쿠폰 등록**: `[1. 선물 쿠폰 코드 풀 등록]` 서식에서 쿠폰 코드를 1개씩 추가하거나 CSV 파일로 일괄 업로드.
3. **수령 범위 지정**:
   - **지정 당첨자 전용**: 당첨된 치지직 채널 ID 명단을 등록한 시청자만 수령 가능.
   - **전체 유저 수령 허용**: `[모든 유저 수령 허용으로 변경]` 클릭 시 로그인한 누구나 선착순 수령.
4. **결과 확인 및 리셋**: 실시간 검색 창으로 수령 내역 확인 및 필요 시 수령 리셋/삭제.

---

## ⚠️ 필수 주의사항 (Cautionary Notes)

> [!CAUTION]
> **1. `.env` 보안키 절대 외부 유출 금지**  
> `CHZZK_CLIENT_SECRET`과 `ADMIN_PASSWORD`가 적힌 `.env` 파일은 GitHub 등 공용 공간에 올리지 마시고, 오직 인수인계받는 담당자에게만 전송해 주세요.

> [!WARNING]
> **2. 네이버 Callback URL 오탈자 주의**  
> 네이버 개발자 센터의 Callback URL과 `.env` 파일의 `CHZZK_REDIRECT_URI`는 토씨 하나 안 틀리고 정확히 `http://localhost:8000/auth/chzzk/callback` 이어야 본인 인증 오류가 나지 않습니다.

> [!IMPORTANT]
> **3. 8000번 포트 중복 실행 주의**  
> 이미 `ChzzkCouponServer.exe`나 다른 서버가 구동 중인 상태에서 중복 실행하면 포트 충돌(`Errno 10048`) 오류가 발생합니다. 기존에 열린 서버 터미널 창을 끄고 재실행해 주세요.

> [!NOTE]
> **4. 외부 시청자 공개 방법 (더블클릭 자동 공개 기능 제공)**  
> 내 컴퓨터에서 연 서버를 시청자들에게 공개할 때는 **`run_public.bat` 파일을 더블클릭**하시면 서버 구동과 동시에 전 세계 시청자용 공개 URL(`https://xxxx.loca.lt`)이 화면에 자동 생성됩니다.
> - 생성된 공개 URL을 **네이버 개발자 센터**의 서비스 URL 및 Callback URL(`https://xxxx.loca.lt/auth/chzzk/callback`)에 등록하고 시청자들에게 공유해 주시면 바로 접속 가능합니다.
> - 또는 무료 도구인 **ngrok** (`ngrok http 8000`)을 활용하셔도 더욱 안정적으로 외부 접속 주소를 띄울 수 있습니다.


---

## 🌐 24시간 무중단 클라우드 배포 가이드 (컴퓨터가 꺼져도 작동하는 방법)

스트리머나 진행자의 컴퓨터가 꺼져 있어도 시청자들이 24시간 언제든 접속해서 쿠폰을 수령하게 하려면 **100% 무료 클라우드 서비스(Render)**를 활용할 수 있습니다.

### Render 배포 3분 가이드
1. **[Render.com](https://render.com/)** 접속 ➔ **`Sign in with GitHub`** 로그인
2. **`New +` ➔ `Web Service`** 클릭 ➔ GitHub 저장소 `ManofKimchi08/chzzk-coupon-app` 선택
3. **설정값 입력**:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: **`Free`**
4. **Environment Variables**에 `.env`에 있던 `CHZZK_CLIENT_ID`, `CHZZK_CLIENT_SECRET`, `ADMIN_PASSWORD` 등 입력 후 **[Create Web Service]** 클릭
5. 완성된 `https://yyyy.onrender.com` 주소를 네이버 개발자 센터 서비스 URL 및 Callback URL에 등록하면 **컴퓨터를 꺼두어도 24시간 자동 동작**합니다!

---

## 📄 라이선스
MIT License

