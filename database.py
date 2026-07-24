import sqlite3
import os
import pandas as pd
from datetime import datetime
from typing import Optional, List, Dict, Any

DB_PATH = os.path.join(os.path.dirname(__file__), "coupons.db")
COUPON_CSV_PATH = os.path.join(os.path.dirname(__file__), "coupons.csv")
WINNERS_CSV_PATH = os.path.join(os.path.dirname(__file__), "winners.csv")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. 쿠폰 풀 테이블 (진행자가 등록한 난수 쿠폰 코드들)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS coupon_pool (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                coupon_code TEXT UNIQUE NOT NULL,
                assigned_channel_id TEXT,
                assigned_nickname TEXT,
                claimed_at TEXT
            )
        """)
        
        # 2. 당첨 대상자 명단 테이블 (지정한 유저만 수령 가능하도록 제한)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS allowed_winners (
                channel_id TEXT PRIMARY KEY,
                nickname TEXT
            )
        """)
        
        # 3. 설정을 위한 옵션 테이블 (예: 전체 유저 수령 허용 여부)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        cursor.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('allow_all_users', 'false')")
        
        conn.commit()
    
    # 시드 데이터 자동 초기화
    sync_initial_seed_data()

def sync_initial_seed_data():
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 쿠폰 풀 초기화
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
        
        # 당첨 대상자 초기화
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

# --- 설정 관리 ---
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

# --- 당첨 대상자 관리 ---
def is_allowed_winner(channel_id: str) -> bool:
    if is_allow_all_users():
        return True
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM allowed_winners WHERE channel_id = ?", (channel_id,))
        return cursor.fetchone() is not None

def add_allowed_winner(channel_id: str, nickname: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO allowed_winners (channel_id, nickname) VALUES (?, ?)", (channel_id.strip(), nickname.strip()))
        conn.commit()

def import_allowed_winners_csv(df: pd.DataFrame) -> int:
    if 'channel_id' not in df.columns:
        raise ValueError("CSV 파일에 'channel_id' 컬럼이 있어야 합니다.")
    count = 0
    with get_connection() as conn:
        cursor = conn.cursor()
        for _, row in df.iterrows():
            c_id = str(row['channel_id']).strip()
            nick = str(row.get('nickname', '치지직시청자')).strip()
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

# --- 쿠폰 풀 관리 및 핵심 무작위 할당 로직 ---
def add_coupon_to_pool(coupon_code: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO coupon_pool (coupon_code) VALUES (?)", (coupon_code.strip(),))
        conn.commit()

def import_coupons_csv(df: pd.DataFrame) -> int:
    # 'coupon_code' 또는 첫 번째 컬럼을 사용
    col = 'coupon_code' if 'coupon_code' in df.columns else df.columns[0]
    count = 0
    with get_connection() as conn:
        cursor = conn.cursor()
        for _, row in df.iterrows():
            code = str(row[col]).strip()
            if code:
                cursor.execute("INSERT OR IGNORE INTO coupon_pool (coupon_code) VALUES (?)", (code,))
                count += 1
        conn.commit()
    return count

def claim_random_coupon(channel_id: str, nickname: str) -> Dict[str, Any]:
    """
    핵심 로직 (보안 및 동시성 완전 보장):
    1. 당첨 대상자 검증
    2. 유저가 이미 발급받은 쿠폰이 있는지 확인 -> 있으면 기존 쿠폰 반환
    3. BEGIN IMMEDIATE 트랜잭션으로 미발급 쿠폰 1개 무작위 선택 후 안전하게 원자적 할당
    """
    if not is_allowed_winner(channel_id):
        return {"success": False, "code": "NOT_WINNER", "message": "당첨 대상자가 아닙니다."}
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        
        # 1. 이미 이 유저에게 발급된 쿠폰이 있는지 확인
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
        
        # 2. 남아있는 미할당 쿠폰 무작위 1개 뽑기
        cursor.execute("SELECT id, coupon_code FROM coupon_pool WHERE assigned_channel_id IS NULL ORDER BY RANDOM() LIMIT 1")
        available = cursor.fetchone()
        
        if not available:
            return {"success": False, "code": "NO_COUPONS", "message": "준비된 모든 선물 쿠폰이 소진되었습니다."}
        
        coupon_id = available["id"]
        coupon_code = available["coupon_code"]
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 3. 원자적 할당 업데이트
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

def get_all_coupons() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
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
