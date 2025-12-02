"""
Fresh migration script for production deployment.
This script:
1. Creates a fresh np_data.db (deleting any existing one)
2. Sets up the v3 multi-carpool schema
3. Creates the three users (christian, eric, sean)
4. Creates the CESpool carpool
5. Migrates all entries from data.db

IMPORTANT: This will DELETE the existing np_data.db file!
"""
import sqlite3
import os
from hashlib import sha256

SOURCE_DB = "data.db"
DEST_DB = "np_data.db"
TARGET_POOL_NAME = "CESpool"

# Mapping Legacy Key -> New Username
USER_MAPPING = {
    "CA": "christian",
    "ER": "eric",
    "SJ": "sean"
}

# Default passwords (CHANGE THESE IN PRODUCTION!)
DEFAULT_PASSWORDS = {
    "christian": "change-me-christian",
    "eric": "change-me-eric",
    "sean": "change-me-sean"
}

def create_fresh_database():
    """Create a fresh np_data.db with v3 schema."""
    if os.path.exists(DEST_DB):
        print(f"⚠️  Deleting existing {DEST_DB}...")
        os.remove(DEST_DB)
    
    print(f"Creating fresh {DEST_DB}...")
    conn = sqlite3.connect(DEST_DB)
    
    # Create v3 multi-carpool schema
    conn.executescript("""
        -- Users table
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1
        );
        
        -- Carpools table
        CREATE TABLE carpools (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );
        
        -- Carpool memberships
        CREATE TABLE carpool_memberships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            carpool_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            member_key TEXT NOT NULL,
            display_name TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            UNIQUE(carpool_id, member_key),
            UNIQUE(carpool_id, user_id),
            FOREIGN KEY(carpool_id) REFERENCES carpools(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        
        -- Entries table
        CREATE TABLE entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day TEXT NOT NULL,
            member_key TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('D','R','O')),
            update_user TEXT DEFAULT 'admin',
            update_ts TEXT DEFAULT (CURRENT_TIMESTAMP),
            update_date TEXT,
            carpool_id INTEGER,
            user_id INTEGER
        );
        
        -- Create unique index for multi-carpool support
        CREATE UNIQUE INDEX idx_entries_cid_day_uid 
        ON entries(carpool_id, day, user_id);
    """)
    
    conn.commit()
    print("✓ Schema created")
    return conn

def create_users(conn):
    """Create the three users."""
    print("\nCreating users...")
    user_ids = {}
    
    for key, username in USER_MAPPING.items():
        password = DEFAULT_PASSWORDS.get(username, "change-me")
        password_hash = sha256(password.encode()).hexdigest()
        
        cursor = conn.execute("""
            INSERT INTO users(username, password_hash, is_admin, active)
            VALUES (?, ?, 1, 1)
        """, (username, password_hash))
        
        user_ids[key] = cursor.lastrowid
        print(f"  ✓ Created user '{username}' (ID: {user_ids[key]}) with password '{password}'")
    
    conn.commit()
    return user_ids

def create_carpool_and_memberships(conn, user_ids):
    """Create CESpool carpool and add members."""
    print(f"\nCreating carpool '{TARGET_POOL_NAME}'...")
    
    cursor = conn.execute("INSERT INTO carpools(name) VALUES (?)", (TARGET_POOL_NAME,))
    pool_id = cursor.lastrowid
    print(f"  ✓ Created carpool (ID: {pool_id})")
    
    print("\nAdding members to carpool...")
    for key, username in USER_MAPPING.items():
        uid = user_ids[key]
        display_name = username.capitalize()
        
        conn.execute("""
            INSERT INTO carpool_memberships(carpool_id, user_id, member_key, display_name, active)
            VALUES (?, ?, ?, ?, 1)
        """, (pool_id, uid, key, display_name))
        
        print(f"  ✓ Added {display_name} (key: {key})")
    
    conn.commit()
    return pool_id

def migrate_entries(src_conn, dst_conn, pool_id, user_ids):
    """Migrate entries from source database."""
    print("\nMigrating entries from data.db...")
    
    rows = src_conn.execute("SELECT * FROM entries").fetchall()
    count = 0
    skipped = 0
    
    for r in rows:
        key = r["member_key"]
        if key not in user_ids:
            skipped += 1
            continue
        
        uid = user_ids[key]
        day = r["day"]
        role = r["role"]
        
        try:
            dst_conn.execute("""
                INSERT INTO entries(carpool_id, day, user_id, member_key, role, update_user, update_ts, update_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, DATE('now'))
            """, (pool_id, day, uid, key, role, "migration_script", r["update_ts"] or ""))
            count += 1
        except Exception as e:
            print(f"  ✗ Error migrating entry {day} {key}: {e}")
    
    dst_conn.commit()
    print(f"✓ Migration complete. Migrated {count} entries. Skipped {skipped}.")
    return count

def main():
    print("=" * 60)
    print("FRESH PRODUCTION MIGRATION")
    print("=" * 60)
    print(f"\nSource: {SOURCE_DB}")
    print(f"Destination: {DEST_DB} (will be DELETED and recreated)")
    print(f"Target Carpool: {TARGET_POOL_NAME}")
    print("\n⚠️  WARNING: This will DELETE the existing np_data.db!")
    
    response = input("\nContinue? (yes/no): ").strip().lower()
    if response != "yes":
        print("Migration cancelled.")
        return
    
    # Check source exists
    if not os.path.exists(SOURCE_DB):
        print(f"\n✗ ERROR: Source database '{SOURCE_DB}' not found!")
        return
    
    # Create fresh database
    dst_conn = create_fresh_database()
    
    # Create users
    user_ids = create_users(dst_conn)
    
    # Create carpool and memberships
    pool_id = create_carpool_and_memberships(dst_conn, user_ids)
    
    # Migrate entries
    src_conn = sqlite3.connect(SOURCE_DB)
    src_conn.row_factory = sqlite3.Row
    
    entry_count = migrate_entries(src_conn, dst_conn, pool_id, user_ids)
    
    # Cleanup
    src_conn.close()
    dst_conn.close()
    
    print("\n" + "=" * 60)
    print("✓ MIGRATION COMPLETE!")
    print("=" * 60)
    print(f"\nSummary:")
    print(f"  - Created {len(user_ids)} users")
    print(f"  - Created 1 carpool: {TARGET_POOL_NAME}")
    print(f"  - Migrated {entry_count} entries")
    print(f"\n⚠️  IMPORTANT: Change the default passwords!")
    print(f"  Current passwords are:")
    for username, password in DEFAULT_PASSWORDS.items():
        print(f"    - {username}: {password}")

if __name__ == "__main__":
    main()
