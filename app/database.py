"""
Database layer — libSQL/Turso driver for Seven Bet.
Uses libsql_experimental (Turso client) for both local development
and production (Vercel) environments.

Environment variables:
  TURSO_DATABASE_URL  — Turso remote URL  
  TURSO_AUTH_TOKEN    — Turso auth token

When both are set: direct remote connection (no local replica).
Fallback: local SQLite file.
"""
import os
import uuid
from typing import Any

import libsql_experimental as libsql

# ── Connection ────────────────────────────────────────────────────
_conn = None
_IS_VERCEL = os.environ.get("VERCEL", "") == "1"

def get_connection():
    global _conn
    if _conn is not None:
        return _conn

    turso_url = os.environ.get("TURSO_DATABASE_URL", "")
    turso_token = os.environ.get("TURSO_AUTH_TOKEN", "")

    try:
        if turso_url and turso_token:
            # Direct remote connection — no sync_url to avoid filesystem writes
            _conn = libsql.connect(database=turso_url, auth_token=turso_token)
        elif os.environ.get("DATABASE_URL", ""):
            # Generic fallback for sandbox/local (sqlite:///path format)
            db_path = os.environ["DATABASE_URL"].replace("sqlite:///", "")
            _conn = libsql.connect(db_path)
        elif _IS_VERCEL:
            # On Vercel without Turso — in-memory (ephemeral)
            _conn = libsql.connect(":memory:")
        else:
            # Local dev: use SQLite file
            db_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "sevenbet.db"
            )
            _conn = libsql.connect(db_path)

        try:
            _conn.execute("PRAGMA journal_mode=WAL")
        except Exception:
            pass

    except Exception as e:
        # If ALL connection attempts fail, create in-memory fallback
        print(f"[WARN] DB connection failed ({e}), using in-memory SQLite")
        _conn = libsql.connect(":memory:")

    return _conn


def run(sql: str) -> list[dict[str, Any]]:
    """Execute SQL and return results as list of dicts."""
    try:
        conn = get_connection()
        cursor = conn.execute(sql)

        # For SELECT queries, return rows as dicts
        if cursor.description:
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]

        # For INSERT/UPDATE/DELETE — libsql auto-commits
        return []
    except Exception as e:
        print(f"[WARN] SQL query failed: {e}")
        print(f"  SQL: {sql[:200]}")
        return []


# ── Schema migration ──────────────────────────────────────────────

def migrate():
    """Create application tables if they don't exist."""
    try:
        # --- app_users ---
        run("""
            CREATE TABLE IF NOT EXISTS app_users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT,
                gold_status TEXT DEFAULT 'free',
                rake_rate REAL DEFAULT 0.07,
                created_at TEXT NOT NULL
            )
        """)

        # --- app_bets ---
        run("""
            CREATE TABLE IF NOT EXISTS app_bets (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                creator_id TEXT NOT NULL,
                stake REAL NOT NULL,
                max_participants INTEGER NOT NULL DEFAULT 2,
                status TEXT NOT NULL DEFAULT 'open',
                winner_id TEXT,
                created_at TEXT NOT NULL,
                settled_at TEXT
            )
        """)

        # --- app_participants ---
        run("""
            CREATE TABLE IF NOT EXISTS app_participants (
                bet_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                joined_at TEXT NOT NULL,
                PRIMARY KEY (bet_id, user_id)
            )
        """)

        # --- app_transactions ---
        run("""
            CREATE TABLE IF NOT EXISTS app_transactions (
                id TEXT PRIMARY KEY,
                bet_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                amount REAL NOT NULL,
                type TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # --- gold_tiers ---
        run("""
            CREATE TABLE IF NOT EXISTS gold_tiers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tier_name TEXT NOT NULL,
                price_gbp REAL NOT NULL,
                rake_rate REAL NOT NULL,
                badge_color TEXT NOT NULL,
                sequence INTEGER NOT NULL
            )
        """)
        run("""
            INSERT OR IGNORE INTO gold_tiers (id, tier_name, price_gbp, rake_rate, badge_color, sequence) VALUES
            (1, 'entry', 49, 0.07, 'bronze', 1),
            (2, 'standard', 199, 0.07, 'silver', 2),
            (3, 'premium', 999, 0.05, 'gold', 3),
            (4, 'patron', 4999, 0.04, 'diamond', 4),
            (5, 'seven', 17777, 0.03, 'black_diamond', 5)
        """)

        # --- gold_users ---
        run("""
            CREATE TABLE IF NOT EXISTS gold_users (
                user_id TEXT PRIMARY KEY,
                tier_id INTEGER NOT NULL,
                activated_at TEXT NOT NULL,
                stripe_payment_id TEXT
            )
        """)

        # --- Backward compat: add balance column if missing ---
        run("ALTER TABLE app_users ADD COLUMN balance REAL DEFAULT 0.0")

        # --- Platform user ---
        run("""
            INSERT OR IGNORE INTO app_users (id, username, email, created_at)
            VALUES ('platform', 'platform', 'platform@bettheseven.com', '2026-06-27T00:00:00Z')
        """)

    except Exception as e:
        print(f"[ERROR] Database migration failed: {e}")


# ── Users ─────────────────────────────────────────────────────────

def create_user(username: str, email: str = "") -> dict[str, Any]:
    uid = str(uuid.uuid4())
    now = _now()
    run(
        f"INSERT INTO app_users (id, username, email, created_at) "
        f"VALUES ('{uid}', '{username}', '{email}', '{now}')"
    )
    return get_user(uid)


def get_user(user_id: str) -> dict[str, Any] | None:
    rows = run(f"SELECT * FROM app_users WHERE id = '{user_id}'")
    return rows[0] if rows else None


def get_user_by_username(username: str) -> dict[str, Any] | None:
    rows = run(f"SELECT * FROM app_users WHERE username = '{username}'")
    return rows[0] if rows else None


def update_balance(user_id: str, delta: float) -> dict[str, Any]:
    run(f"UPDATE app_users SET balance = balance + {delta} WHERE id = '{user_id}'")
    return get_user(user_id)


def update_user_gold_status(user_id: str, status: str, rake_rate: float):
    run(f"UPDATE app_users SET gold_status = '{status}', rake_rate = {rake_rate} WHERE id = '{user_id}'")


def list_users() -> list[dict[str, Any]]:
    return run("SELECT * FROM app_users ORDER BY created_at DESC")


# ── Bets ──────────────────────────────────────────────────────────

def create_bet(title: str, creator_id: str, stake: float, max_participants: int = 2) -> dict[str, Any]:
    bid = str(uuid.uuid4())
    now = _now()
    run(
        f"INSERT INTO app_bets (id, title, creator_id, stake, max_participants, status, created_at) "
        f"VALUES ('{bid}', '{title}', '{creator_id}', {stake}, {max_participants}, 'open', '{now}')"
    )
    return get_bet(bid)


def get_bet(bet_id: str) -> dict[str, Any] | None:
    rows = run(f"SELECT * FROM app_bets WHERE id = '{bet_id}'")
    return rows[0] if rows else None


def list_bets(status: str | None = None) -> list[dict[str, Any]]:
    if status:
        return run(f"SELECT * FROM app_bets WHERE status = '{status}' ORDER BY created_at DESC")
    return run("SELECT * FROM app_bets ORDER BY created_at DESC")


def join_bet(bet_id: str, user_id: str):
    now = _now()
    run(
        f"INSERT OR IGNORE INTO app_participants (bet_id, user_id, joined_at) "
        f"VALUES ('{bet_id}', '{user_id}', '{now}')"
    )


def get_participants(bet_id: str) -> list[dict[str, Any]]:
    return run(
        f"SELECT u.id, u.username, u.email, p.joined_at "
        f"FROM app_participants p "
        f"JOIN app_users u ON u.id = p.user_id "
        f"WHERE p.bet_id = '{bet_id}'"
    )


def count_participants(bet_id: str) -> int:
    rows = run(f"SELECT COUNT(*) as cnt FROM app_participants WHERE bet_id = '{bet_id}'")
    return rows[0]["cnt"] if rows else 0


def update_bet_status(bet_id: str, status: str, winner_id: str | None = None):
    if winner_id:
        now = _now()
        run(
            f"UPDATE app_bets SET status = '{status}', winner_id = '{winner_id}', settled_at = '{now}' "
            f"WHERE id = '{bet_id}'"
        )
    else:
        run(f"UPDATE app_bets SET status = '{status}' WHERE id = '{bet_id}'")


# ── Transactions ──────────────────────────────────────────────────

def add_transaction(bet_id: str, user_id: str, amount: float, tx_type: str):
    tid = str(uuid.uuid4())
    now = _now()
    run(
        f"INSERT INTO app_transactions (id, bet_id, user_id, amount, type, created_at) "
        f"VALUES ('{tid}', '{bet_id}', '{user_id}', {amount}, '{tx_type}', '{now}')"
    )


def get_user_transactions(user_id: str) -> list[dict[str, Any]]:
    return run(
        f"SELECT * FROM app_transactions WHERE user_id = '{user_id}' ORDER BY created_at DESC"
    )


def get_bet_transactions(bet_id: str) -> list[dict[str, Any]]:
    return run(
        f"SELECT * FROM app_transactions WHERE bet_id = '{bet_id}' ORDER BY created_at DESC"
    )


def get_user_bets(user_id: str) -> list[dict[str, Any]]:
    return run(
        f"SELECT b.* FROM app_bets b "
        f"JOIN app_participants p ON p.bet_id = b.id "
        f"WHERE p.user_id = '{user_id}' "
        f"ORDER BY b.created_at DESC"
    )


# ── Platform Stats ────────────────────────────────────────────────

def platform_stats() -> dict[str, Any]:
    handle = run("SELECT COALESCE(SUM(ABS(amount)), 0) as total FROM app_transactions WHERE type = 'stake'")
    rake = run("SELECT COALESCE(SUM(amount), 0) as total FROM app_transactions WHERE type = 'rake'")
    active = run("SELECT COUNT(*) as cnt FROM app_bets WHERE status IN ('open', 'accepted')")
    settled = run("SELECT COUNT(*) as cnt FROM app_bets WHERE status = 'settled'")
    total_bets = run("SELECT COUNT(*) as cnt FROM app_bets")
    return {
        "total_handle": handle[0]["total"] if handle else 0,
        "rake_collected": rake[0]["total"] if rake else 0,
        "active_bets": active[0]["cnt"] if active else 0,
        "settled_bets": settled[0]["cnt"] if settled else 0,
        "total_bets": total_bets[0]["cnt"] if total_bets else 0,
    }


def leaderboard(limit: int = 10) -> list[dict[str, Any]]:
    return run(
        f"SELECT u.id, u.username, "
        f"COALESCE(SUM(CASE WHEN t.type = 'stake' THEN ABS(t.amount) ELSE 0 END), 0) as total_staked, "
        f"COALESCE(SUM(CASE WHEN t.type = 'payout' THEN t.amount ELSE 0 END), 0) as total_won "
        f"FROM app_users u "
        f"LEFT JOIN app_transactions t ON t.user_id = u.id "
        f"WHERE u.id != 'platform' "
        f"GROUP BY u.id "
        f"ORDER BY total_staked DESC "
        f"LIMIT {limit}"
    )


# ── Helpers ───────────────────────────────────────────────────────

def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()