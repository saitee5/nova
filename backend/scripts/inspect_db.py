import sqlite3

def inspect():
    con = sqlite3.connect('backend/vigil.db')
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [r[0] for r in cur.fetchall()]
    print("DATABASE: backend/vigil.db")
    print(f"TOTAL TABLES: {len(tables)}")
    for t in sorted(tables):
        cur.execute(f"SELECT count(*) FROM {t}")
        count = cur.fetchone()[0]
        print(f"  {t:30}: {count:6} rows")

if __name__ == "__main__":
    inspect()
