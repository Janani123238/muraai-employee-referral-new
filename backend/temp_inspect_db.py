import sqlite3
from pathlib import Path

root_db = Path(__file__).resolve().parent.parent / 'muraai.db'
print('root_db', root_db)
print('exists', root_db.exists())
if root_db.exists():
    conn = sqlite3.connect(str(root_db))
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    print('tables', cur.fetchall())
    if 'users' in [row[0] for row in cur.fetchall()]:
        cur.execute("SELECT id, name, email, role FROM users LIMIT 20")
        print(cur.fetchall())
    conn.close()
