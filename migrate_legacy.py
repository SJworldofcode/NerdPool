import sqlite3
import os

SOURCE_DB = "data.db"
DEST_DB = "np_data.db"
TARGET_POOL_NAME = "CESpool"

# Mapping Legacy Key -> New Username
USER_MAPPING = {
    "CA": "christian",
    "ER": "eric",
    "SJ": "sean"
}

def migrate():
    if not os.path.exists(SOURCE_DB):
        print(f"Source DB {SOURCE_DB} not found!")
        return

    print(f"Migrating from {SOURCE_DB} to {DEST_DB}...")
    
    src = sqlite3.connect(SOURCE_DB)
    src.row_factory = sqlite3.Row
    
    dst = sqlite3.connect(DEST_DB)
    dst.row_factory = sqlite3.Row
    
    # 1. Get or Create Target Pool
    pool = dst.execute("SELECT id FROM carpools WHERE name=?", (TARGET_POOL_NAME,)).fetchone()
    if not pool:
        print(f"Creating carpool '{TARGET_POOL_NAME}'...")
        cursor = dst.execute("INSERT INTO carpools(name) VALUES (?)", (TARGET_POOL_NAME,))
        pool_id = cursor.lastrowid
    else:
        pool_id = pool["id"]
        print(f"Found carpool '{TARGET_POOL_NAME}' (ID: {pool_id})")

    # 2. Resolve User IDs and Ensure Memberships
    user_ids = {} # Key -> ID
    
    for key, username in USER_MAPPING.items():
        # Find user
        u = dst.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if not u:
            print(f"WARNING: User '{username}' not found in destination DB. Skipping {key}.")
            continue
        
        uid = u["id"]
        user_ids[key] = uid
        
        # Ensure membership
        mem = dst.execute(
            "SELECT * FROM carpool_memberships WHERE carpool_id=? AND user_id=?", 
            (pool_id, uid)
        ).fetchone()
        
        if not mem:
            print(f"Adding {username} to {TARGET_POOL_NAME}...")
            dst.execute("""
                INSERT INTO carpool_memberships(carpool_id, user_id, member_key, display_name, active)
                VALUES (?, ?, ?, ?, 1)
            """, (pool_id, uid, key, username.capitalize()))
        else:
            print(f"User {username} is already a member.")

    # 3. Migrate Entries
    print("Migrating entries...")
    rows = src.execute("SELECT * FROM entries").fetchall()
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
        
        # Insert into new entries table
        # Schema: carpool_id, day, user_id, member_key, role, update_user, update_ts, update_date
        try:
            dst.execute("""
                INSERT INTO entries(carpool_id, day, user_id, member_key, role, update_user, update_ts, update_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, DATE('now'))
                ON CONFLICT(carpool_id, day, user_id) DO UPDATE SET
                  role=excluded.role,
                  member_key=excluded.member_key
            """, (pool_id, day, uid, key, role, "migration_script", r["update_ts"] or ""))
            count += 1
        except Exception as e:
            print(f"Error migrating entry {day} {key}: {e}")
            
    dst.commit()
    print(f"Migration complete. Migrated {count} entries. Skipped {skipped}.")
    
    src.close()
    dst.close()

if __name__ == "__main__":
    migrate()
