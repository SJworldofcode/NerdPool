
import sqlite3
import sys

def fix():
    print("Fixing production schema...")
    db_path = "np_data.db"
    
    # Allow overriding db path for testing
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
        
    print(f"Connecting to {db_path}...")
    db = sqlite3.connect(db_path)
    
    try:
        # 1. Check existing indexes
        print("Checking existing indexes on 'entries'...")
        cur = db.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='entries'")
        indexes = cur.fetchall()
        
        has_correct_index = False
        for name, sql in indexes:
            print(f"  - Found index: {name}")
            # loose check if it covers the 3 columns
            if "carpool_id" in sql and "day" in sql and "user_id" in sql:
                has_correct_index = True
                print("    -> Looks like a matching unique index.")

        if has_correct_index:
            print("A matching unique index already exists. Attempting to ensure it is named idx_entries_cid_day_uid...")
        
        # 2. Create the standard unique index
        # We use IF NOT EXISTS, but if there's a different named index with same columns, SQLite allows multiple indexes.
        # But for ON CONFLICT to work, we need *a* unique constraint.
        print("Creating unique index 'idx_entries_cid_day_uid'...")
        db.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_entries_cid_day_uid 
            ON entries(carpool_id, day, user_id)
        """)
        print("Success: Index created (or already existed).")
        
        db.commit()
        print("Schema fix applied successfully.")
        
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix()
