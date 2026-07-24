import sqlite3
import os
import html
import pandas as pd
from datetime import datetime
from typing import Optional, List, Dict, Any

DB_PATH = os.path.join(os.path.dirname(__file__), "coupons.db")

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

def import_allowed_winners_csv(df: pd.DataFrame) -> int:
    if 'channel_id' not in df.columns:
        raise ValueError("CSV 파일에 'channel_id' 컬럼이 있어야 합니다.")
    count = 0
    with get_connection() as conn:
        cursor = conn.cursor()
        for _, row in df.iterrows():
            c_id = html.escape(str(row['channel_id']).strip())
            nick = html.escape(str(row.get('nickname', '치지직시청자')).strip())
            cursor.execute("INSERT OR REPLACE INTO allowed_winners (channel_id, nickname) VALUES (?, ?)", (c_id, nick))
            count += 1
        conn.commit()
    return count

def get_allowed_winners() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM allowed_winners")
        return [dict(row) for row in cursor.fetchall()]

def delete_allowed_winner(channel_id: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM allowed_winners WHERE channel_id = ?", (channel_id,))
        conn.commit()

# --- 쿠폰 풀 관리 및 무작위 할당 ---
def add_coupon_to_pool(coupon_code: str):
    clean_code = html.escape(coupon_code.strip())
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO coupon_pool (coupon_code) VALUES (?)", (clean_code,))
        conn.commit()

def import_coupons_csv(df: pd.DataFrame) -> int:
    col = 'coupon_code' if 'coupon_code' in df.columns else df.columns[0]
    count = 0
    with get_connection() as conn:
        cursor = conn.cursor()
        for _, row in df.iterrows():
            code = html.escape(str(row[col]).strip())
            if code:
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
