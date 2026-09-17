import sqlite3
from pathlib import Path
p = Path(__file__).resolve().parent.parent / 'muraai.db'
print('db', p)
print('exists', p.exists())
conn = sqlite3.connect(str(p))
cur = conn.cursor()
cur.execute("SELECT id, name, email, role, is_active FROM users WHERE role IN ('admin','system_admin','chro','vp','cto','hr','hr_manager') ORDER BY id")
rows = cur.fetchall()
print('admin_rows', len(rows))
for row in rows:
    print(row)
conn.close()
