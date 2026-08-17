import sqlite3
import re
from datetime import datetime

DB_NAME = "leads.db"


def db_connect():
    connect_db = sqlite3.connect(DB_NAME)
    connect_db.row_factory = sqlite3.Row
    connect_db.execute("PRAGMA journal_mode=WAL;")
    connect_db.execute("PRAGMA busy_timeout = 30000;")
    return connect_db


def get_create_lead(phone_number: str):
    con = db_connect()
    cursor = con.cursor()

    cursor.execute(
        "SELECT id FROM leads WHERE phone_number=?", (phone_number,)
    )
    row = cursor.fetchone()
    if row:
        lead_id = row["id"]
    else:
        cursor.execute(
            "INSERT INTO leads (phone_number) VALUES (?)", (phone_number,)
        )
        con.commit()
        lead_id = cursor.lastrowid
    con.close()
    return lead_id


def init_db():
    con = db_connect()
    cursor = con.cursor()

    # 1. Added 'BOTH' to CHECK constraint
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS leads(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT UNIQUE NOT NULL,
            client_name TEXT,
            intent TEXT CHECK(intent IN ('BUY', 'SELL', 'BOTH', 'INQUERY')),
            lead_tag TEXT CHECK(lead_tag IN ('HOT','WARM','COLD')),
            is_alerted INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )        
        """
    )

    # 2. Changed lead_id type from TEXT to INTEGER UNIQUE
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS seller_properties(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER UNIQUE NOT NULL,
            ownership_type TEXT,
            land_are TEXT,
            mouza_location TEXT,
            doc_type TEXT,
            asking_price TEXT,
            FOREIGN KEY (lead_id) REFERENCES leads (id) ON DELETE CASCADE
        )        
        """
    )

    # 3. Added UNIQUE to lead_id to avoid duplicate preference entries
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS buyer_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER UNIQUE NOT NULL,
            preferred_location TEXT,
            property_type TEXT,
            budget_range TEXT,
            FOREIGN KEY (lead_id) REFERENCES leads (id) ON DELETE CASCADE
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS conversation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            sender TEXT CHECK(sender IN ('CLIENT', 'BOT')),
            message_text TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES leads (id) ON DELETE CASCADE
        )
    """
    )

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS properties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            property_type TEXT NOT NULL, 
            intent_type TEXT NOT NULL,  
            location_mouza TEXT NOT NULL,
            land_area TEXT NOT NULL,
            asking_price REAL NOT NULL,
            ownership_type TEXT,        
            doc_type TEXT,            
            description TEXT,
            image_url TEXT,
            status TEXT DEFAULT 'AVAILABLE', 
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

    con.commit()
    con.close()
    print("💾 Connection initialized with the leads database")


def converse_log(lead_id: int, sender: str, message_text: str):
    con = db_connect()
    cursor = con.cursor()
    cursor.execute(
        "INSERT INTO conversation_logs(lead_id, sender, message_text) VALUES(?,?,?)",
        (lead_id, sender, message_text),
    )
    con.commit()
    con.close()


def update_lead_info(lead_id: int, name: str = None, intent: str = None, tag: str = None):
    con = db_connect()
    cursor = con.cursor()
    cursor.execute(
        """
        UPDATE leads 
        SET client_name = COALESCE(?, client_name),
            intent = COALESCE(?, intent),
            lead_tag = COALESCE(?, lead_tag),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """,
        (name, intent, tag, lead_id),
    )
    con.commit()
    con.close()


def get_history(lead_id: int, limit: int = 20):
    con = db_connect()
    cursor = con.cursor()
    cursor.execute(
        """
        SELECT sender, message_text 
        FROM conversation_logs 
        WHERE lead_id = ? 
        ORDER BY timestamp DESC LIMIT ?
    """,
        (lead_id, limit),
    )
    rows = cursor.fetchall()
    con.close()
    history = []

    for row in reversed(rows):
        history.append(f"{row['sender']}: {row['message_text']}")
    return "\n".join(history)


def get_properties():
    """Fetch active inventory with IDs to feed into the bot prompt."""
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, property_type, location_mouza, land_area, asking_price, description, image_url 
        FROM properties 
        WHERE status = 'AVAILABLE'
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return "No inventory currently listed."

    formatted_listings = []
    for r in rows:
        has_photo = "Yes" if r["image_url"] else "No"
        formatted_listings.append(
            f"- [ID: {r['id']}] {r['title']} | Type: {r['property_type']} | Location: {r['location_mouza']} | Size: {r['land_area']} | Price: PKR {r['asking_price']:,.0f} | Photo Available: {has_photo} | Details: {r['description']}"
        )
    return "\n".join(formatted_listings)


def get_property_by_id(property_id: int):
    """Retrieves a single property record from the properties table by its integer ID."""
    if not property_id:
        return None
    try:
        property_id = int(property_id)
    except (ValueError, TypeError):
        return None

    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM properties WHERE id = ?", (property_id,))
    row = cursor.fetchone()
    conn.close()
    return row


def get_last_matched_property_id(lead_id: int):
    """Scans conversation logs to find the most recent property ID discussed with this lead."""
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT message_text FROM conversation_logs 
        WHERE lead_id = ? AND sender = 'BOT' 
        ORDER BY timestamp DESC LIMIT 5
    """, (lead_id,))
    rows = cursor.fetchall()
    conn.close()

    for r in rows:
        msg_text = r["message_text"]
        match = re.search(r'\[ID:\s*(\d+)\]', msg_text)
        if match:
            return int(match.group(1))
    return None


def save_buyer(lead_id: int, location: str = None, prop_type: str = None, budget: str = None):
    con = db_connect()
    cursor = con.cursor()
    cursor.execute("SELECT id FROM buyer_preferences WHERE lead_id = ?", (lead_id,))
    exists = cursor.fetchone()
    if exists:
        cursor.execute(
            """
            UPDATE buyer_preferences 
            SET preferred_location = COALESCE(?, preferred_location),
                property_type = COALESCE(?, property_type),
                budget_range = COALESCE(?, budget_range)
            WHERE lead_id = ?
        """,
            (location, prop_type, budget, lead_id),
        )
    else:
        cursor.execute(
            """
            INSERT INTO buyer_preferences (lead_id, preferred_location, property_type, budget_range)
            VALUES (?, ?, ?, ?)
        """,
            (lead_id, location, prop_type, budget),
        )
    con.commit()
    con.close()


def save_seller(lead_id: int, ownership: str = None, area: str = None, mouza: str = None, doc_type: str = None, price: str = None):
    con = db_connect()
    cursor = con.cursor()
    cursor.execute("SELECT id FROM seller_properties WHERE lead_id = ?", (lead_id,))
    exists = cursor.fetchone()
    if exists:
        cursor.execute(
            """
            UPDATE seller_properties
            SET ownership_type = COALESCE(?, ownership_type),
                land_are = COALESCE(?, land_are),
                mouza_location = COALESCE(?, mouza_location),
                doc_type = COALESCE(?, doc_type),
                asking_price = COALESCE(?, asking_price)
            WHERE lead_id = ?
        """,
            (ownership, area, mouza, doc_type, price, lead_id),
        )
    else:
        cursor.execute(
            """
            INSERT INTO seller_properties (lead_id, ownership_type, land_are, mouza_location, doc_type, asking_price)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (lead_id, ownership, area, mouza, doc_type, price),
        )
    con.commit()
    con.close()


if __name__ == "__main__":
    init_db()