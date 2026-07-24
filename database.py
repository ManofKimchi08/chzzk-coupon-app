import sqlite3
import os
import io
import html
import pandas as pd
from datetime import datetime
from typing import Optional, List, Dict, Any

import sys

if getattr(sys, 'frozen', False):
    DB_PATH = os.path.join(os.path.dirname(sys.executable), "coupons.db")
else:
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "coupons.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. 쿠폰 풀 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS coupon_pool (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                coupon_code TEXT UNIQUE NOT NULL,
                assigned_channel_id TEXT,
                assigned_nickname TEXT,
                claimed_at TEXT
            )
        """)
        
        # 2. 당첨 대상자 명단 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS allowed_winners (
                channel_id TEXT PRIMARY KEY,
                nickname TEXT
            )
        """)
        
        # 3. 설정을 위한 옵션 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        cursor.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('allow_all_users', 'false')")
        cursor.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('event_notice', '치지직 본인 인증으로 1회성 선물 쿠폰 코드를 무작위 수령하세요.')")
        cursor.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('admin_password', 'streamer123!')")
        
        conn.commit()

    
    sync_initial_seed_data()

def sync_initial_seed_data():
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM coupon_pool")
        if cursor.fetchone()[0] == 0:
            sample_coupons = [
                "CHZZK-POOL-8A92-4912",
                "CHZZK-POOL-77B1-9920",
                "CHZZK-POOL-33X9-1029",
                "CHZZK-POOL-9999-WNNR",
                "CHZZK-POOL-5555-GOLD"
            ]
            for code in sample_coupons:
                cursor.execute("INSERT OR IGNORE INTO coupon_pool (coupon_code) VALUES (?)", (code,))
        
        cursor.execute("SELECT COUNT(*) FROM allowed_winners")
        if cursor.fetchone()[0] == 0:
            sample_winners = [
                ("test_user_01", "트위치치지직팬01"),
                ("test_user_02", "게임마스터_김치지"),
                ("test_user_03", "스트리머열혈팬"),
                ("streamer_channel_123", "진행자스트리머")
            ]
            for c_id, nick in sample_winners:
                cursor.execute("INSERT OR IGNORE INTO allowed_winners (channel_id, nickname) VALUES (?, ?)", (c_id, nick))
        
        conn.commit()

# --- 설정 및 공지사항 관리 ---
def is_allow_all_users() -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM config WHERE key = 'allow_all_users'")
        row = cursor.fetchone()
        return row and row[0].lower() == 'true'

def set_allow_all_users(allow: bool):
    val_str = 'true' if allow else 'false'
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('allow_all_users', ?)", (val_str,))
        conn.commit()

def get_event_notice() -> str:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM config WHERE key = 'event_notice'")
        row = cursor.fetchone()
        return row[0] if row else "치지직 본인 인증으로 1회성 선물 쿠폰 코드를 무작위 수령하세요."

def set_event_notice(notice: str):
    sanitized_notice = html.escape(notice.strip())
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('event_notice', ?)", (sanitized_notice,))
        conn.commit()

def get_admin_password() -> str:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM config WHERE key = 'admin_password'")
        row = cursor.fetchone()
        if row and row[0]:
            return row[0]
    return os.getenv("ADMIN_PASSWORD", "streamer123!")

def set_admin_password(new_pass: str):
    clean_pass = new_pass.strip()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('admin_password', ?)", (clean_pass,))
        conn.commit()


# --- 당첨 대상자 관리 ---
def is_allowed_winner(channel_id: str) -> bool:
    if is_allow_all_users():
        return True
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM allowed_winners WHERE channel_id = ?", (channel_id,))
        return cursor.fetchone() is not None

def add_allowed_winner(channel_id: str, nickname: str):
    clean_id = html.escape(channel_id.strip())
    clean_nick = html.escape(nickname.strip())
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO allowed_winners (channel_id, nickname) VALUES (?, ?)", (clean_id, clean_nick))
        conn.commit()

def read_csv_robustly(contents: bytes) -> pd.DataFrame:
    """UTF-8 BOM, CP949, EUC-KR 등 한국어 엑셀 CSV 인코딩 및 구분자(쉼표, 세미콜론, 탭)를 자동 감지하여 읽는 함수"""
    encodings = ['utf-8-sig', 'cp949', 'euc-kr', 'utf-8', 'latin-1']
    for enc in encodings:
        try:
            text = contents.decode(enc)
            first_line = text.splitlines()[0] if text.splitlines() else ""
            sep = ';' if ';' in first_line and ',' not in first_line else ('\t' if '\t' in first_line and ',' not in first_line else ',')
            df = pd.read_csv(io.StringIO(text), sep=sep)
            df.columns = [str(c).strip().lstrip('\ufeff') for c in df.columns]
            return df
        except Exception:
            continue
    raise ValueError("CSV 파일의 인코딩을 해석할 수 없습니다. UTF-8 또는 CP949(EUC-KR) 형식인지 확인해 주세요.")

import re

def import_allowed_winners_csv(df: pd.DataFrame) -> int:
    seq_blacklist = {'no', 'num', 'number', 'index', 'idx', 'seq', 'sequence', '순번', '번호', '연번', '순서', 'count', 'n'}
    high_channel_keys = ['channel_id', 'channelid', 'channel_hash', 'chzzk_id', 'chzzk_channel_id', '채널id', '채널아이디', '채널_id', '채널고유id', '고유id', '고유아이디']
    low_channel_keys = ['channel', 'user_id', 'userid', '유저id', '유저아이디']
    nick_keys = ['nickname', 'nick', '닉네임', '이름', 'user', 'username', '시청자', '시청자명', '유저명', '당첨자', '당첨자명']

    col_map = {str(col).strip().lower().replace(" ", "_").replace("-", "_"): col for col in df.columns}
    channel_col, nickname_col = None, None

    # Step 1: 헤더 명칭 우선 매칭
    for key in high_channel_keys:
        if key in col_map:
            channel_col = col_map[key]
            break

    for key in nick_keys:
        if key in col_map:
            nickname_col = col_map[key]
            break

    if not channel_col:
        for key in low_channel_keys:
            if key in col_map and key not in seq_blacklist:
                channel_col = col_map[key]
                break

    # Step 2: 헤더로 명확히 찾지 못한 경우 데이터 내용(휴리스틱 점수) 분석
    def is_sequence_col(series):
        vals = [str(x).strip() for x in series.dropna() if str(x).strip() and str(x).strip().lower() != 'nan']
        if not vals:
            return True
        return all(x.isdigit() and len(x) <= 5 for x in vals)

    def channel_id_score(series):
        vals = [str(x).strip() for x in series.dropna() if str(x).strip() and str(x).strip().lower() != 'nan']
        if not vals:
            return -100
        if is_sequence_col(series):
            return -50
        score = 0
        for val in vals:
            if len(val) == 32 and re.match(r'^[0-9a-fA-F]{32}$', val):
                score += 10
            elif len(val) >= 6 and not val.isdigit():
                score += 5
            elif re.search(r'[a-zA-Z_]', val):
                score += 3
        return score

    def nickname_score(series):
        vals = [str(x).strip() for x in series.dropna() if str(x).strip() and str(x).strip().lower() != 'nan']
        if not vals:
            return -100
        if is_sequence_col(series):
            return -50
        score = 0
        for val in vals:
            if re.search(r'[가-힣]', val):
                score += 5
            elif not val.isdigit():
                score += 2
        return score

    cols_to_check = [c for c in df.columns if c != nickname_col and str(c).strip().lower().replace(" ", "_").replace("-", "_") not in seq_blacklist]

    if not channel_col and cols_to_check:
        best_col = max(cols_to_check, key=lambda c: channel_id_score(df[c]))
        if channel_id_score(df[best_col]) > -20:
            channel_col = best_col

    if not nickname_col:
        remaining = [c for c in df.columns if c != channel_col and str(c).strip().lower().replace(" ", "_").replace("-", "_") not in seq_blacklist]
        if remaining:
            best_nick = max(remaining, key=lambda c: nickname_score(df[c]))
            if nickname_score(df[best_nick]) > -20:
                nickname_col = best_nick

    if not channel_col:
        non_seq = [c for c in df.columns if str(c).strip().lower().replace(" ", "_").replace("-", "_") not in seq_blacklist]
        if non_seq:
            channel_col = non_seq[0]
        elif len(df.columns) > 0:
            channel_col = df.columns[0]
        else:
            raise ValueError("CSV 파일에 데이터를 읽을 수 있는 컬럼이 없습니다.")

    count = 0
    with get_connection() as conn:
        cursor = conn.cursor()
        for _, row in df.iterrows():
            val = str(row[channel_col]).strip() if pd.notna(row[channel_col]) else ""
            if not val or val.lower() == 'nan':
                continue
            c_id = html.escape(val)
            
            nick_val = ""
            if nickname_col and pd.notna(row[nickname_col]):
                nick_val = str(row[nickname_col]).strip()
            if not nick_val or nick_val.lower() == 'nan':
                nick_val = "치지직시청자"
            nick = html.escape(nick_val)
            
            cursor.execute("INSERT OR REPLACE INTO allowed_winners (channel_id, nickname) VALUES (?, ?)", (c_id, nick))
            count += 1
        conn.commit()
    return count

def get_allowed_winners(search_query: str = None) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT 
                w.channel_id, 
                w.nickname,
                c.coupon_code,
                c.claimed_at
            FROM allowed_winners w
            LEFT JOIN coupon_pool c ON w.channel_id = c.assigned_channel_id
        """
        params = []
        if search_query and search_query.strip():
            s = f"%{search_query.strip()}%"
            query += " WHERE w.channel_id LIKE ? OR w.nickname LIKE ? OR c.coupon_code LIKE ?"
            params.extend([s, s, s])
            
        query += " ORDER BY w.channel_id ASC"
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

def delete_allowed_winner(channel_id: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM allowed_winners WHERE channel_id = ?", (channel_id,))
        conn.commit()

def clear_all_allowed_winners() -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM allowed_winners")
        count = cursor.rowcount
        conn.commit()
        return count

# --- 쿠폰 풀 관리 및 무작위 할당 ---
def add_coupon_to_pool(coupon_code: str):
    clean_code = html.escape(coupon_code.strip())
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO coupon_pool (coupon_code) VALUES (?)", (clean_code,))
        conn.commit()

def import_coupons_csv(df: pd.DataFrame) -> int:
    seq_blacklist = {'no', 'num', 'number', 'index', 'idx', 'seq', 'sequence', '순번', '번호', '연번', '순서', 'count', 'n'}
    col_map = {str(col).strip().lower().replace(" ", "_").replace("-", "_"): col for col in df.columns}

    coupon_col = None
    possible_coupon_keys = ['coupon_code', 'couponcode', 'coupon', 'code', '쿠폰', '쿠폰코드', '쿠폰_코드', '핀번호', 'pin']
    for key in possible_coupon_keys:
        if key in col_map:
            coupon_col = col_map[key]
            break

    if not coupon_col:
        non_seq_cols = [c for c in df.columns if str(c).strip().lower().replace(" ", "_").replace("-", "_") not in seq_blacklist]
        coupon_col = non_seq_cols[0] if non_seq_cols else df.columns[0]

    count = 0
    with get_connection() as conn:
        cursor = conn.cursor()
        for _, row in df.iterrows():
            val = str(row[coupon_col]).strip() if pd.notna(row[coupon_col]) else ""
            if not val or val.lower() == 'nan':
                continue
            code = html.escape(val)
            cursor.execute("INSERT OR IGNORE INTO coupon_pool (coupon_code) VALUES (?)", (code,))
            count += 1
        conn.commit()
    return count

def claim_random_coupon(channel_id: str, nickname: str) -> Dict[str, Any]:
    if not is_allowed_winner(channel_id):
        return {"success": False, "code": "NOT_WINNER", "message": "당첨 대상자가 아닙니다."}
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        
        cursor.execute("SELECT * FROM coupon_pool WHERE assigned_channel_id = ?", (channel_id,))
        existing = cursor.fetchone()
        if existing:
            row_dict = dict(existing)
            return {
                "success": False,
                "code": "ALREADY_CLAIMED",
                "message": "이미 수령 완료된 쿠폰이 존재합니다.",
                "coupon_code": row_dict["coupon_code"],
                "claimed_at": row_dict["claimed_at"]
            }
        
        cursor.execute("SELECT id, coupon_code FROM coupon_pool WHERE assigned_channel_id IS NULL ORDER BY RANDOM() LIMIT 1")
        available = cursor.fetchone()
        
        if not available:
            return {"success": False, "code": "NO_COUPONS", "message": "준비된 모든 선물 쿠폰이 소진되었습니다."}
        
        coupon_id = available["id"]
        coupon_code = available["coupon_code"]
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute("""
            UPDATE coupon_pool
            SET assigned_channel_id = ?, assigned_nickname = ?, claimed_at = ?
            WHERE id = ? AND assigned_channel_id IS NULL
        """, (channel_id, nickname, now_str, coupon_id))
        
        if cursor.rowcount > 0:
            conn.commit()
            return {
                "success": True,
                "code": "SUCCESS",
                "coupon_code": coupon_code,
                "nickname": nickname,
                "claimed_at": now_str
            }
        else:
            conn.rollback()
            return {"success": False, "code": "RETRY", "message": "발급 진행 중 충돌이 발생했습니다. 다시 시도해 주세요."}

def get_coupon_pool_stats() -> Dict[str, int]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM coupon_pool")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM coupon_pool WHERE assigned_channel_id IS NOT NULL")
        assigned = cursor.fetchone()[0]
        
        return {
            "total": total,
            "assigned": assigned,
            "remaining": total - assigned
        }

def get_all_coupons(search_query: str = None) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        if search_query:
            q = f"%{search_query.strip()}%"
            cursor.execute("""
                SELECT * FROM coupon_pool 
                WHERE coupon_code LIKE ? OR assigned_channel_id LIKE ? OR assigned_nickname LIKE ?
                ORDER BY id DESC
            """, (q, q, q))
        else:
            cursor.execute("SELECT * FROM coupon_pool ORDER BY id DESC")
        return [dict(row) for row in cursor.fetchall()]

def reset_coupon_assignment(coupon_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE coupon_pool
            SET assigned_channel_id = NULL, assigned_nickname = NULL, claimed_at = NULL
            WHERE id = ?
        """, (coupon_id,))
        conn.commit()

def delete_coupon_from_pool(coupon_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM coupon_pool WHERE id = ?", (coupon_id,))
        conn.commit()

def clear_all_coupons() -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM coupon_pool")
        count = cursor.rowcount
        conn.commit()
        return count
