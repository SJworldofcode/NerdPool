
import sqlite3
import sys
import os

def update_db():
    print("Updating production database schema...")
    db_path = "np_data.db"
    
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
        
    if not os.path.exists(db_path):
        print(f"Error: Database file '{db_path}' not found.")
        return

    print(f"Connecting to {db_path}...")
    db = sqlite3.connect(db_path)
    
    try:
        # 1. Add 'active' column to 'carpools' table
        print("\n[1/2] Checking 'carpools' table for 'active' column...")
        cur = db.execute("PRAGMA table_info(carpools)")
        cols = [r[1] for r in cur.fetchall()]
        if "active" in cols:
            print("   -> 'active' column already exists. Skipping.")
        else:
            print("   -> Column missing. Adding 'active' column...")
            db.execute("ALTER TABLE carpools ADD COLUMN active INTEGER NOT NULL DEFAULT 1")
            print("   -> Success.")

        # 2. Add Unique Index for ON CONFLICT support
        print("\n[2/2] Checking unique index on 'entries' table...")
        # Check if we already have a covering unique index
        cur = db.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='entries'")
        indexes = cur.fetchall()
        
        has_correct_index = False
        for name, sql in indexes:
            if "carpool_id" in sql and "day" in sql and "user_id" in sql and "UNIQUE" in sql.upper():
                has_correct_index = True
                print(f"   -> Found existing unique index: {name}")
                break

        if has_correct_index:
            print("   -> Unique index already exists. Skipping.")
        else:
            print("   -> Index missing. Creating 'idx_entries_cid_day_uid'...")
            db.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_entries_cid_day_uid 
                ON entries(carpool_id, day, user_id)
            """)
            print("   -> Success.")
        
        db.commit()
        print("\nDone! Database is up to date.")
        
    except Exception as e:
        print(f"\nError during update: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    update_db()
