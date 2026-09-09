import sqlite3

conn = sqlite3.connect("leads.db")
cursor = conn.cursor()

# Enable WAL mode
cursor.execute("PRAGMA journal_mode=WAL;")

# 1. Ensure tables exist (with the missing comma fixed for image)
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
    price_per_marla REAL DEFAULT 0.0,
    marlas REAL DEFAULT 0.0,
    image TEXT
);
""")

# 2. Insert 10 Dummy Leads
leads_data = [
    ("+923001234567", "Ali Khan", "BUYING", "House", "5 Marla", "DHA Phase 2", 15000000, 20000000, "NEW", 1),
    ("+923012345678", "Usman Tariq", "RENT", "Apartment", "2 Bed", "Blue Area", 50000, 70000, "FOLLOW UP", 1),
    ("+923023456789", "Ayesha Malik", "BUYING", "Plot", "10 Marla", "Bahria Town", 8000000, 12000000, "NEW", 1),
    ("+923034567890", "Bilal Ahmed", "SELLING", "Commercial", "Plaza", "Saddar", 40000000, 50000000, "NEW", 1),
    ("+923045678901", "Zainab Noor", "AWAITING INFO", "House", "1 Kanal", "Gulberg", 45000000, 60000000, "FOLLOW UP", 1),
    ("+923056789012", "Hamza Sheikh", "BUYING", "House", "10 Marla", "DHA Phase 1", 25000000, 30000000, "NEW", 1),
    ("+923067890123", "Fatima Zahra", "RENT", "Portion", "3 Bed", "F-7", 120000, 150000, "CLOSED", 1),
    ("+923078901234", "Omar Farooq", "BUYING", "Plot", "5 Marla", "Faisal Town", 6000000, 9000000, "NEW", 1),
    ("+923089012345", "Sara Ahmed", "SELLING", "House", "10 Marla", "Air Avenue", 22000000, 25000000, "FOLLOW UP", 1),
    ("+923090123456", "Kamran Akmal", "RENT", "Apartment", "1 Bed", "DHA Phase 5", 40000, 60000, "NEW", 1),
    ("+923089012315", "Sara Ahmead", "SELLING", "House", "10 Marla", "Air Avenue", 22000000, 25000000, "FOLLOW UP", 1),
    ("+923090123416", "Kamran asAkmal", "RENT", "Apartment", "1 Bed", "DHA Phase 5", 40000, 60000, "NEW", 1)
]

cursor.executemany("""
INSERT OR IGNORE INTO leads (phone_number, name, intent, property_type, area, location, budget_min, budget_max, status, bot_enabled)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", leads_data)

# 3. Insert 10 Dummy Inventory Items
inventory_data = [
    ("5 Marla Brand New House in DHA Phase 2", "PKR 1.85 Crore", "House", "DHA Phase 2", 4, 5, 2250, "AVAILABLE", "2026-09-01", 3500000.0, 5.0, "https://images.unsplash.com/photo-1580587771525-78b9dba3b914"),
    ("Luxury 2-Bed Furnished Apartment in Blue Area", "PKR 65,000", "Apartment", "Blue Area", 2, 2, 1100, "AVAILABLE", "2026-09-02", 0.0, 0.0, "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00"),
    ("10 Marla Residential Plot Prime Location", "PKR 1.05 Crore", "Plot", "Bahria Town", 0, 0, 2700, "AVAILABLE", "2026-09-03", 1050000.0, 10.0, "https://images.unsplash.com/photo-1500382017468-9049fed747ef"),
    ("Commercial Plaza Building Main Boulevard", "PKR 4.5 Crore", "Commercial", "Saddar", 0, 6, 5400, "AVAILABLE", "2026-09-04", 9000000.0, 15.0, "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab"),
    ("1 Kanal Modern Designer Villa", "PKR 5.2 Crore", "House", "Gulberg", 6, 7, 5400, "AVAILABLE", "2026-09-05", 26000000.0, 20.0, "https://images.unsplash.com/photo-1600585154340-be6161a56a0c"),
    ("5 Marla Corner Plot Near Park", "PKR 75 Lakh", "Plot", "Faisal Town", 0, 0, 1350, "AVAILABLE", "2026-09-06", 1500000.0, 5.0, "https://images.unsplash.com/photo-1524813686514-a57563d77840"),
    ("3-Bed Upper Portion in F-7/2", "PKR 1.35 Lakh", "Portion", "F-7", 3, 3, 2000, "AVAILABLE", "2026-09-07", 0.0, 0.0, "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688"),
    ("10 Marla Spanish Design House", "PKR 2.4 Crore", "House", "DHA Phase 1", 5, 6, 3100, "AVAILABLE", "2026-09-08", 2400000.0, 10.0, "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9"),
    ("1-Bed Executive Studio Apartment", "PKR 50,000", "Apartment", "DHA Phase 5", 1, 1, 650, "AVAILABLE", "2026-09-09", 0.0, 0.0, "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267"),
    ("8 Marla Commercial Shop Floor", "PKR 1.8 Crore", "Commercial", "Bahria Town", 0, 2, 1800, "AVAILABLE", "2026-09-10", 2250000.0, 8.0, "https://images.unsplash.com/photo-1497366216548-37526070297c")
]

cursor.executemany("""
INSERT INTO inventory (title, price, type, location, beds, baths, sqft, status, date_added, price_per_marla, marlas, image)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", inventory_data)

conn.commit()
conn.close()

print("🚀 Successfully seeded 10 leads and 10 properties into leads.db!")