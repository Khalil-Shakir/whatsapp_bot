# backend/init_db.py
import sqlite3

conn = sqlite3.connect("leads.db")
cursor = conn.cursor()

# Enable Write-Ahead Logging (WAL) for concurrent read/write support
cursor.execute("PRAGMA journal_mode=WAL;")

cursor.execute("""
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone_number TEXT UNIQUE NOT NULL,
    name TEXT,
    intent TEXT CHECK(intent IN ('BUYING', 'SELLING', 'RENT', 'AWAITING INFO')),
    property_type TEXT,
    area TEXT,
    location TEXT,
    budget_min REAL,
    budget_max REAL,
    status TEXT DEFAULT 'NEW' CHECK(status IN ('NEW', 'FOLLOW UP',  'CLOSED')),
    bot_enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            price TEXT NOT NULL,
            type TEXT NOT NULL,
            location TEXT NOT NULL,
            beds INTEGER DEFAULT 0,
            baths INTEGER DEFAULT 0,
            sqft INTEGER DEFAULT 0,
            status TEXT DEFAULT 'AVAILABLE',
            date_added TEXT NOT NULL,
            price_per_marla REAL,
            marlas REAL
            image TEXT
        )
    """)
try:
    cursor.execute("ALTER TABLE inventory ADD COLUMN price_per_marla REAL DEFAULT 0.0;")
    cursor.execute("ALTER TABLE inventory ADD COLUMN marlas REAL DEFAULT 0.0;")
except sqlite3.OperationalError:
    pass  # Column already exists

conn.commit()
conn.close()
print("Database initialized successfully!")