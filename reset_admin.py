#!/usr/bin/env python3
import os, sys, sqlite3, argparse, hashlib, textwrap

DEFAULT_PW = "change-me"

def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def resolve_db_path(cli_db: str | None) -> str:
    if cli_db:
        return os.path.abspath(cli_db)
    # 1) env TP_POOL_DB, then DATABASE_URL
    env_path = os.environ.get("TP_POOL_DB") or os.environ.get("DATABASE_URL")
    if env_path:
        return os.path.abspath(env_path)
    # 2) constants.DATABASE_URL (project default)
    try:
        import constants  # type: ignore
        dburl = getattr(constants, "DATABASE_URL", None)
        if dburl:
            return os.path.abspath(dburl) if os.path.isabs(dburl) else os.path.abspath(dburl)
    except Exception:
        pass
    # 3) final fallback: local np_Data.db
    return os.path.abspath("np_data.db")

def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(
        db_path,
        detect_types=sqlite3.PARSE_DECLTYPES,
        check_same_thread=False,
        timeout=30.0,
        isolation_level=None,  # autocommit-style
    )
    conn.row_factory = sqlite3.Row
    # pragmas
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
    return bool(row)

def ensure_users_table(conn: sqlite3.Connection):
    # Create if missing (minimal set)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT UNIQUE NOT NULL,
          password_hash TEXT NOT NULL,
          is_admin INTEGER NOT NULL DEFAULT 0
        );
    """)
    # Add 'active' column if missing
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "active" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN active INTEGER NOT NULL DEFAULT 1")

def upsert_admin(conn: sqlite3.Connection, username: str, password: str, make_admin: bool):
    pw_hash = sha256_hex(password)
    is_admin = 1 if make_admin else 0
    conn.execute("""
        INSERT INTO users(username, password_hash, is_admin, active)
        VALUES (?, ?, ?, 1)
        ON CONFLICT(username) DO UPDATE SET
            password_hash=excluded.password_hash,
            is_admin=excluded.is_admin,
            active=1
    """, (username, pw_hash, is_admin))
    # Optionally ensure user_prefs is present (harmless if you’re not using it)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_prefs (
          user_id INTEGER PRIMARY KEY,
          miles_per_ride REAL NOT NULL DEFAULT 36.0,
          gas_price      REAL NOT NULL DEFAULT 4.78,
          avg_mpg        REAL NOT NULL DEFAULT 22.0,
          FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)
    # Seed prefs row if missing
    row = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
    if row:
        conn.execute("""
            INSERT OR IGNORE INTO user_prefs(user_id) VALUES (?)
        """, (row["id"],))
    conn.commit()

def list_users(conn: sqlite3.Connection):
    rows = conn.execute("SELECT id, username, is_admin, COALESCE(active,1) AS active FROM users ORDER BY username").fetchall()
    print("\nUsers:")
    for r in rows:
        print(f"  - {r['id']:>3}  {r['username']:<20}  admin={'yes' if r['is_admin'] else 'no'}  active={'yes' if r['active'] else 'no'}")
    if not rows:
        print("  (none)")

def main():
    p = argparse.ArgumentParser(
        description="Reset or create an admin user in the NerdPool (carpool) SQLite DB.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            Examples:
              python reset_admin.py
              python reset_admin.py --db C:\\data\\np_data.db
              python reset_admin.py --username admin --password change-me
        """),
    )
    p.add_argument("--db", help="Path to SQLite DB (overrides env and constants.DATABASE_URL)")
    p.add_argument("--username", default="admin", help="Username to reset/create (default: admin)")
    p.add_argument("--password", default=DEFAULT_PW, help=f"Password to set (default: {DEFAULT_PW})")
    p.add_argument("--no-admin", action="store_true", help="Do NOT grant admin (sets is_admin=0)")
    p.add_argument("--show-users", action="store_true", help="List users after reset")
    args = p.parse_args()

    db_path = resolve_db_path(args.db)
    print(f"Using DB: {db_path}")

    if not os.path.exists(db_path):
        # Create the file on first open by connecting
        open(db_path, "a").close()

    conn = connect(db_path)
    try:
        ensure_users_table(conn)
        upsert_admin(conn, args.username, args.password, not args.no_admin)
        print(f"User '{args.username}' is set. Password = '{args.password}'  (SHA-256)")
        if args.show_users:
            list_users(conn)
        print("Done.")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
