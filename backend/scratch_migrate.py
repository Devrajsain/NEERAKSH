import sqlite3
conn = sqlite3.connect('slicktrace.db')
c = conn.cursor()
c.execute('PRAGMA foreign_keys=off;')
c.execute('BEGIN TRANSACTION;')

c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='vessels'")
sql = c.fetchone()[0]

sql_new = sql.replace('speed_kts VARCHAR NOT NULL', 'speed_kts FLOAT').replace('heading_deg FLOAT NOT NULL', 'heading_deg FLOAT').replace('vessels', 'vessels_new', 1)

c.execute(sql_new)
c.execute('INSERT INTO vessels_new SELECT * FROM vessels')
c.execute('DROP TABLE vessels')
c.execute('ALTER TABLE vessels_new RENAME TO vessels')
c.execute('COMMIT;')
c.execute('PRAGMA foreign_keys=on;')
print("Migration completed.")
