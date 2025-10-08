# db.py
import os
import sqlite3
from hashlib import sha256
from flask import g, current_app

def _resolve_db_path() -> str:
    env_path = os.environ.get("NP_POOL_DB") or os.environ.get("DATABASE_URL")
    if env_path:
        return os.path.abspath(env_path)
    try:
        app_path = getattr(current_app, "database_url", None)
        if app_path:
            return os.path.abspath(app_path)
    except Exception:
        pass
    try:
        from constants import DATABASE_URL as CONST_DB_URL  # type: ignore
        if CONST_DB_URL:
            return os.path.abspath(
                CONST_DB_URL if os.path.isabs(CONST_DB_URL)
                else os.path.join(os.path.dirname(__file__), CONST_DB_URL)
            )
    except Exception:
        pass
    return os.path.join(os.path.dirname(__file__), "np_data.db")

def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(
        db_path,
        detect_types=sqlite3.PARSE_DECLTYPES,
        check_same_thread=False,
        timeout=10.0,
        isolation_level=None,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def get_db():
    if "db" not in g:
        db_path = _resolve_db_path()
        g.db = _connect(db_path)
        _ensure_schema(g.db)
        _migrate_v2(g.db)
        _migrate_users_active(g.db)
        # existing migration in your project
        _migrate_v3_prefs(g.db)  # NEW: per-user prefs for miles/gas/mpg
        _migrate_v3_multicarpool(g.db)
        _migrate_v4_user_carpool_prefs(g.db)
    return g.db

def _ensure_schema(db: sqlite3.Connection):
    db.executescript("""
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
          update_date TEXT,
          UNIQUE(day, member_key)
        );
    """)

    # Seed members from legacy constants if empty (kept for backward compat)
    have = db.execute("SELECT COUNT(*) AS n FROM members").fetchone()["n"]
    if have == 0:
        try:
            from constants import MEMBERS  # optional legacy import
        except Exception:
            MEMBERS = {}
        for k, v in MEMBERS.items():
            db.execute(
                "INSERT OR IGNORE INTO members(key, name, active) VALUES (?,?,1)",
                (k, v),
            )

    # Seed admin user if missing
    have_admin = db.execute("SELECT COUNT(*) AS n FROM users WHERE username='admin'").fetchone()["n"]
    if have_admin == 0:
        db.execute(
            "INSERT OR IGNORE INTO users(username, password_hash, is_admin) VALUES (?,?,1)",
            ("admin", sha256(b"change-me").hexdigest()),
        )
    db.commit()

def _migrate_users_active(db):
    cols = {r["name"] for r in db.execute("PRAGMA table_info(users)").fetchall()}
    if "active" not in cols:
        db.execute("ALTER TABLE users ADD COLUMN active INTEGER NOT NULL DEFAULT 1")
        # default everyone to active
        db.execute("UPDATE users SET active = 1 WHERE active IS NULL")
        db.commit()


def _migrate_v2(db: sqlite3.Connection):
    cols = {r["name"] for r in db.execute("PRAGMA table_info(entries)").fetchall()}
    altered = False
    if "update_user" not in cols:
        db.execute("ALTER TABLE entries ADD COLUMN update_user TEXT DEFAULT 'admin'")
        altered = True
    if "update_ts" not in cols:
        db.execute("ALTER TABLE entries ADD COLUMN update_ts TEXT DEFAULT (CURRENT_TIMESTAMP)")
        altered = True
    if "update_date" not in cols:
        db.execute("ALTER TABLE entries ADD COLUMN update_date TEXT")
        altered = True
    if altered:
        db.execute("""
            UPDATE entries
            SET update_user = COALESCE(update_user, 'admin'),
                update_ts   = COALESCE(update_ts, CURRENT_TIMESTAMP)
        """)
        db.commit()

def _migrate_v3_prefs(db: sqlite3.Connection):
    """
    Per-user preferences for miles_per_ride, gas_price, avg_mpg.
    Defaults: 36.0, 4.78, 22.0 (migrated from old constants).
    """
    db.executescript("""
        CREATE TABLE IF NOT EXISTS user_prefs (
          user_id INTEGER PRIMARY KEY,
          miles_per_ride REAL NOT NULL DEFAULT 36.0,
          gas_price      REAL NOT NULL DEFAULT 4.78,
          avg_mpg        REAL NOT NULL DEFAULT 22.0,
          FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)
    # Seed prefs for any users that don't have them yet
    db.execute("""
        INSERT OR IGNORE INTO user_prefs(user_id, miles_per_ride, gas_price, avg_mpg)
        SELECT id, 36.0, 4.78, 22.0 FROM users
    """)
    db.commit()

# --- add in db.py ---
def _migrate_v3_multicarpool(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS carpools (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS carpool_memberships (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          carpool_id INTEGER NOT NULL,
          user_id    INTEGER NOT NULL,
          member_key TEXT NOT NULL,
          display_name TEXT NOT NULL,
          active INTEGER NOT NULL DEFAULT 1,
          UNIQUE(carpool_id, member_key),
          UNIQUE(carpool_id, user_id),
          FOREIGN KEY(carpool_id) REFERENCES carpools(id) ON DELETE CASCADE,
          FOREIGN KEY(user_id)    REFERENCES users(id)    ON DELETE CASCADE
        );
    """)
    # add columns to entries if missing
    cols = {r["name"] for r in db.execute("PRAGMA table_info(entries)").fetchall()}
    if "carpool_id" not in cols:
        db.execute("ALTER TABLE entries ADD COLUMN carpool_id INTEGER")
    if "user_id" not in cols:
        db.execute("ALTER TABLE entries ADD COLUMN user_id INTEGER")
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_entries_v3 ON entries(carpool_id, day, user_id)")
    db.commit()

def _migrate_v4_user_carpool_prefs(db):
    """
    Per-user, per-carpool preference for miles_per_ride.
    Global gas_price and avg_mpg stay in user_prefs.
    """
    db.executescript("""
        CREATE TABLE IF NOT EXISTS user_carpool_prefs (
          user_id    INTEGER NOT NULL,
          carpool_id INTEGER NOT NULL,
          miles_per_ride REAL NOT NULL DEFAULT 36.0,
          PRIMARY KEY (user_id, carpool_id),
          FOREIGN KEY (user_id)    REFERENCES users(id)    ON DELETE CASCADE,
          FOREIGN KEY (carpool_id) REFERENCES carpools(id) ON DELETE CASCADE
        );
    """)
    # Seed defaults for existing memberships
    db.execute("""
        INSERT OR IGNORE INTO user_carpool_prefs(user_id, carpool_id, miles_per_ride)
        SELECT cm.user_id, cm.carpool_id, 36.0
        FROM carpool_memberships cm
    """)
    db.commit()



def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()
