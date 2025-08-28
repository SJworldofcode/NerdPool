#!/usr/bin/env python3
"""
Utility CLI for CESpool on local + PythonAnywhere.

Examples:
  python manage.py stats
  python manage.py users
  python manage.py set-user --username admin --password "ChangeMeNow!" --admin 1
  python manage.py migrate
  python manage.py seed-members
  python manage.py backup --out data.backup.db
  python manage.py wal-checkpoint
  python manage.py vacuum
"""
import os
import sys
import argparse
from hashlib import sha256

# Ensure project root on sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Import your app + db utilities
from app_v2 import create_app
from db import get_db, close_db

def with_app_context(fn):
    """Decorator to run a function inside Flask app context and return its result."""
    def _wrap(*args, **kwargs):
        app = create_app()
        with app.app_context():
            return fn(*args, **kwargs)
    return _wrap

@with_app_context
def cmd_stats(args):
    db = get_db()
    dblist = db.execute("PRAGMA database_list").fetchall()
    main_path = [r["file"] if "file" in r.keys() else r[2] for r in dblist if (r["name"] if "name" in r.keys() else r[1]) == "main"][0]
    tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY 1").fetchall()]
    entries = db.execute("SELECT COUNT(*) FROM entries").fetchone()[0] if "entries" in tables else 0
    users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0] if "users" in tables else 0
    members = db.execute("SELECT COUNT(*) FROM members").fetchone()[0] if "members" in tables else 0
    print("DB path:", main_path)
    print("Tables:", ", ".join(tables) or "(none)")
    print("Counts: entries=%s users=%s members=%s" % (entries, users, members))

@with_app_context
def cmd_users(args):
    db = get_db()
    try:
        rows = db.execute("SELECT id, username, is_admin FROM users ORDER BY username").fetchall()
    except Exception as e:
        print("users table not found:", e)
        return 1
    if not rows:
        print("(no users)")
        return 0
    w = max(5, max(len(r["username"]) for r in rows))
    print(f"{'id':>3}  {'username':<{w}}  admin")
    print("-" * (10 + w))
    for r in rows:
        print(f"{r['id']:>3}  {r['username']:<{w}}  {'yes' if r['is_admin'] else 'no'}")
    return 0

@with_app_context
def cmd_set_user(args):
    db = get_db()
    if not args.username or not args.password:
        print("username and password required")
        return 2
    pw_hash = sha256(args.password.encode()).hexdigest()
    is_admin = 1 if args.admin else 0
    db.execute(
        "INSERT OR REPLACE INTO users(username, password_hash, is_admin) VALUES(?,?,?)",
        (args.username, pw_hash, is_admin),
    )
    db.commit()
    print(f"user '{args.username}' saved (admin={bool(is_admin)})")
    return 0

@with_app_context
def cmd_migrate(args):
    # touching get_db() runs your _ensure_schema + _migrate_v2
    db = get_db()
    # nudge a pragma to force open/commit
    db.execute("PRAGMA user_version")
    db.commit()
    print("schema/migrations ensured")
    return 0

@with_app_context
def cmd_seed_members(args):
    """Re-run the member seeding if table is empty."""
    db = get_db()
    have = db.execute("SELECT COUNT(*) AS n FROM members").fetchone()["n"]
    if have:
        print(f"members already present (count={have}); nothing to do")
        return 0
    # Reuse ensure_schema path by temporarily deleting table? Safer: pull MEMBERS and insert.
    try:
        from constants import MEMBERS
    except Exception:
        MEMBERS = {}
    for k, v in MEMBERS.items():
        db.execute("INSERT OR IGNORE INTO members(key, name, active) VALUES (?,?,1)", (k, v))
    db.commit()
    print(f"seeded {len(MEMBERS)} members")
    return 0

@with_app_context
def cmd_backup(args):
    """Make a SQLite online backup to the given output file."""
    out = os.path.abspath(args.out or "data.backup.db")
    db = get_db()
    # Use SQLite backup API
    dest = __import__("sqlite3").connect(out)
    with dest:
        db.backup(dest)
    dest.close()
    print("backup written to:", out)
    return 0

@with_app_context
def cmd_wal_checkpoint(args):
    db = get_db()
    # checkpoint and truncate WAL so data.db contains the latest state
    db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    db.commit()
    print("WAL checkpointed (TRUNCATE)")

@with_app_context
def cmd_vacuum(args):
    db = get_db()
    db.execute("VACUUM")
    print("VACUUM done")

def main():
    p = argparse.ArgumentParser(prog="manage.py", description="CESpool maintenance CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("stats", help="Show DB path, tables, and row counts").set_defaults(func=cmd_stats)
    sub.add_parser("users", help="List users").set_defaults(func=cmd_users)

    sp = sub.add_parser("set-user", help="Create/update a user (password hashed with sha256)")
    sp.add_argument("--username", required=True)
    sp.add_argument("--password", required=True)
    sp.add_argument("--admin", type=int, choices=[0,1], default=0, help="1=admin, 0=non-admin")
    sp.set_defaults(func=cmd_set_user)

    sub.add_parser("migrate", help="Ensure schema + run lightweight migrations").set_defaults(func=cmd_migrate)
    sub.add_parser("seed-members", help="Seed members table if empty").set_defaults(func=cmd_seed_members)

    bp = sub.add_parser("backup", help="Write a safe online backup of the DB")
    bp.add_argument("--out", default="data.backup.db")
    bp.set_defaults(func=cmd_backup)

    sub.add_parser("wal-checkpoint", help="Checkpoint WAL (TRUNCATE)").set_defaults(func=cmd_wal_checkpoint)
    sub.add_parser("vacuum", help="VACUUM the database").set_defaults(func=cmd_vacuum)

    args = p.parse_args()
    sys.exit(args.func(args))

if __name__ == "__main__":
    main()
