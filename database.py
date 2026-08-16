import sqlite3
from datetime import datetime

DB_NAME = "leads.db"


def db_connect():
    connect_db = sqlite3.connect(DB_NAME)
    connect_db.row_factory = sqlite3.Row
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

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS leads(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT UNIQUE NOT NULL,
            client_name TEXT,
            intent TEXT CHECK(intent IN ('BUY', 'SELL', 'INQUERY')),
            lead_tag CHECK(lead_tag IN ('HOT','WARM','COLD')),
            is_alerted INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )        
        """
    )

    cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS seller_properties(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id TEXT UNIQUE NOT NULL,
                ownership_type TEXT,
                land_are TEXT,
                mouza_location TEXT,
                doc_type TEXT,
                asking_price TEXT,
                FOREIGN KEY (lead_id) REFERENCES leads (id) ON DELETE CASCADE
            )        
            """
        )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS buyer_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
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

    con.commit()
    con.close()
    print("💾 Connection initialized with the leads database")

def converse_log(lead_id: int, sender:str, message_text:str):
    con = db_connect()
    cursor = con.cursor()
    cursor.execute(
        "INSERT INTO conversation_logs(lead_id, sender, message_text) VALUES(?,?,?)",(lead_id, sender, message_text)
    )
    con.commit()
    con.close()

def update_lead_info(lead_id:int, name:str = None, intent:str = None, tag:str = None):
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
#History
def get_history(lead_id: str, limit: int = 10):
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
#Save buyer preferences
def save_buyer(lead_id:int, location:str = None, prop_type:str = None, budget:str = None):
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
#Save seller properties
def save_seller(lead_id:int, ownership:str = None, area:str = None, mouza:str = None, doc_type:str = None, price:str = None):
    con = db_connect()
    cursor = con.cursor()
    cursor.execute("SELECT id FROM seller_properties WHERE lead_id = ?", (lead_id,))
    exists = cursor.fetchone()
    if exists:
        cursor.execute(
            """
            UPDATE seller_properties
            set ownership_type = COALESCE(?, ownership_type),
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