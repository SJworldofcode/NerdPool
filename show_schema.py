
import sqlite3

def check():
    db = sqlite3.connect("np_data.db")
    try:
        cur = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='entries'")
        row = cur.fetchone()
        if row:
            print("--- entries schema ---")
            print(row[0])
        else:
            print("Table 'entries' not found.")
            
        print("\n--- entries indexes ---")
        cur = db.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='entries'")
        for r in cur.fetchall():
            print(f"Index: {r[0]}")
            print(f"SQL: {r[1]}")
            print("-" * 20)
    finally:
        db.close()

if __name__ == "__main__":
    check()
