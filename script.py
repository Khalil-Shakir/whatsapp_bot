import sqlite3
conn = sqlite3.connect("leads.db")
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(buyer_preferences);")
print([row[1] for row in cursor.fetchall()])
conn.close()