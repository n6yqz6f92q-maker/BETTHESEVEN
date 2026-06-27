"""
Database layer — wraps the team-db CLI for all access.
Never use sqlite3 directly; always go through this module.
"""
import json
import subprocess
import uuid
from typing import Any

TEAM_DB = "team-db"


def run(sql: str) -> list[dict[str, Any]]:
    """Execute a single SQL statement via team-db and return parsed JSON."""
    result = subprocess.run(
        [TEAM_DB, sql],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"team-db error: {result.stderr}")
    if not result.stdout.strip():
        return []
    return json.loads(result.stdout)


# ── Schema migration ──────────────────────────────────────────────

def migrate():
    """Create application tables if they don't exist."""
    run("""
        CREATE TABLE IF NOT EXISTS app_users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            balance REAL NOT NULL DEFAULT 0.0,
            created_at TEXT NOT NULL
        )
    """)
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
            settled_at TEXT,
            FOREIGN KEY (creator_id) REFERENCES app_users(id)
        )
    """)
    run("""
        CREATE TABLE IF NOT EXISTS app_participants (
            bet_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            joined_at TEXT NOT NULL,
            PRIMARY KEY (bet_id, user_id),
            FOREIGN KEY (bet_id) REFERENCES app_bets(id),
            FOREIGN KEY (user_id) REFERENCES app_users(id)
        )
    """)
    run("""
        CREATE TABLE IF NOT EXISTS app_transactions (
            id TEXT PRIMARY KEY,
            bet_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            amount REAL NOT NULL,
            type TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (bet_id) REFERENCES app_bets(id),
            FOREIGN KEY (user_id) REFERENCES app_users(id)
        )
    """)
    # Seed platform account if not exists
    run("""
        INSERT OR IGNORE INTO app_users (id, username, email, balance, created_at)
        VALUES ('platform', 'platform', 'platform@sevenbet', 0.0, '2024-01-01T00:00:00Z')
    """)


# ── Users ─────────────────────────────────────────────────────────

def create_user(username: str, email: str | None = None) -> dict[str, Any]:
    uid = str(uuid.uuid4())
    now = _now()
    run(
        f"INSERT INTO app_users (id, username, email, balance, created_at) "
        f"VALUES ('{uid}', '{username}', "
        f"{'NULL' if email is None else f"'{email}'"}, "
        f"0.0, '{now}')"
    )
    return get_user(uid)


def get_user(user_id: str) -> dict[str, Any] | None:
    rows = run(f"SELECT * FROM app_users WHERE id = '{user_id}'")
    return rows[0] if rows else None


def get_user_by_username(username: str) -> dict[str, Any] | None:
    rows = run(f"SELECT * FROM app_users WHERE username = '{username}'")
    return rows[0] if rows else None


def update_balance(user_id: str, delta: float) -> dict[str, Any]:
    """Add delta to user's balance (can be negative for deduction)."""
    run(f"UPDATE app_users SET balance = balance + {delta} WHERE id = '{user_id}'")
    return get_user(user_id)


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
    """Get all bets a user has participated in."""
    return run(
        f"SELECT b.* FROM app_bets b "
        f"JOIN app_participants p ON p.bet_id = b.id "
        f"WHERE p.user_id = '{user_id}' "
        f"ORDER BY b.created_at DESC"
    )


# ── Platform Stats ────────────────────────────────────────────────

def platform_stats() -> dict[str, Any]:
    """Return handle (total wagered), rake collected, active bet count."""
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
    """Top users by net betting volume (total stake placed)."""
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