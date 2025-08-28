# db.py
import os
import sqlite3
from hashlib import sha256
from flask import g, current_app

# ---- DB path resolution (portable + overrideable) ---------------------------
# Order of precedence (first match wins):
# 1) env CESPOOL_DB
# 2) env DATABASE_URL (common host var)
# 3) current_app.database_url (set in app factory)
# 4) constants.DATABASE_URL (project default)
# 5) ./data.db (next to this file)
def _resolve_db_path() -> str:
    # 1 & 2: environment overrides
    env_path = os.environ.get("CESPOOL_DB") or os.environ.get("DATABASE_URL")
    if env_path:
        return os.path.abspath(env_path)

    # 3: app-provided path (only valid inside app context)
    try:
        app_path = getattr(current_app, "database_url", None)
        if app_path:
            return os.path.abspath(app_path)
    except Exception:
        pass

    # 4: project default from constants (optional)
    try:
        from constants import DATABASE_URL as CONST_DB_URL  # type: ignore
        if CONST_DB_URL:
            return os.path.abspath(
                CONST_DB_URL if os.path.isabs(CONST_DB_URL)
                else os.path.join(os.path.dirname(__file__), CONST_DB_URL)
            )
    except Exception:
        pass

    # 5: fallback next to this file
    return os.path.join(os.path.dirname(__file__), "data.db")


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(
        db_path,
        detect_types=sqlite3.PARSE_DECLTYPES,
        check_same_thread=False,
        timeout=10.0,
        isolation_level=None,  # autocommit-style; explicit transactions still work
    )
    conn.row_factory = sqlite3.Row
    # Pragmas: reasonable defaults for a small Flask app
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def get_db():
    """Get a per-request SQLite connection; ensure schema/migrations exist."""
    if "db" not in g:
        db_path = _resolve_db_path()
        g.db = _connect(db_path)
        _ensure_schema(g.db)
        _migrate_v2(g.db)
    return g.db


def _ensure_schema(db: sqlite3.Connection):
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT UNIQUE NOT NULL,
          password_hash TEXT NOT NULL,
          is_admin INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS members (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          key TEXT UNIQUE NOT NULL,
          name TEXT NOT NULL,
          active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS entries (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          day TEXT NOT NULL,
          member_key TEXT NOT NULL,
          role TEXT NOT NULL CHECK(role IN ('D','R','O')),
          update_user TEXT DEFAULT 'admin',
          update_ts   TEXT DEFAULT (CURRENT_TIMESTAMP),
          UNIQUE(day, member_key)
        );
        """
    )

    # Seed default members (optional)
    have = db.execute("SELECT COUNT(*) AS n FROM members").fetchone()["n"]
    if have == 0:
        try:
            from constants import MEMBERS  # lazy import to avoid circulars
        except Exception:
            MEMBERS = {}
        for k, v in MEMBERS.items():
            db.execute(
                "INSERT OR IGNORE INTO members(key, name, active) VALUES (?,?,1)",
                (k, v),
            )

    # Seed admin (only if none exist)
    have_admin = db.execute(
        "SELECT COUNT(*) AS n FROM users WHERE username='admin'"
    ).fetchone()["n"]
    if have_admin == 0:
        db.execute(
            "INSERT OR IGNORE INTO users(username, password_hash, is_admin) VALUES (?,?,1)",
            ("admin", sha256(b"change-me").hexdigest()),
        )

    db.commit()


def _migrate_v2(db: sqlite3.Connection):
    """Add columns introduced in v2 if they’re missing."""
    cols = {r["name"] for r in db.execute("PRAGMA table_info(entries)").fetchall()}
    altered = False
    if "update_user" not in cols:
        db.execute("ALTER TABLE entries ADD COLUMN update_user TEXT DEFAULT 'admin'")
        altered = True
    if "update_ts" not in cols:
        db.execute("ALTER TABLE entries ADD COLUMN update_ts TEXT DEFAULT (CURRENT_TIMESTAMP)")
        altered = True
    if altered:
        db.execute(
            """
            UPDATE entries
            SET update_user = COALESCE(update_user, 'admin'),
                update_ts   = COALESCE(update_ts, CURRENT_TIMESTAMP)
            """
        )
        db.commit()


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()
