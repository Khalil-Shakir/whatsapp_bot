import sqlite3
import re
import os
from datetime import (datetime, date)

DB_NAME = "leads.db"


def db_connect():
    connect_db = sqlite3.connect(DB_NAME)
    connect_db.row_factory = sqlite3.Row
    connect_db.execute("PRAGMA journal_mode=WAL;")
    connect_db.execute("PRAGMA busy_timeout = 30000;")
    return connect_db

def format_pk_phone(phone_str: str) -> str:
    """Sanitizes phone numbers to clean Pakistani format: 923XXXXXXXXX."""
    if not phone_str:
        return ""
    # Strip @s.whatsapp.net or non-digit chars
    digits = re.sub(r'\D', '', str(phone_str))
    
    if digits.startswith("03") and len(digits) == 11:
        return "92" + digits[1:]
    elif digits.startswith("923") and len(digits) == 12:
        return digits
    elif digits.startswith("3") and len(digits) == 10:
        return "92" + digits
    return digits


def update_lead_phone(current_lead_id: int, phone_number: str) -> int:
    """Updates or merges lead records when a valid Pakistani phone number is provided."""
    clean_phone = format_pk_phone(phone_number)
    if not clean_phone:
        return current_lead_id

    con = db_connect()
    cursor = con.cursor()

    try:
        # Check if the phone number already exists under a different lead ID
        cursor.execute("SELECT id FROM leads WHERE phone_number = ?", (clean_phone,))
        existing_lead = cursor.fetchone()

        if existing_lead and existing_lead["id"] != current_lead_id:
            existing_id = existing_lead["id"]
            
            # Reassign message history from temporary lead to the existing lead
            cursor.execute("UPDATE messages SET lead_id = ? WHERE lead_id = ?", (existing_id, current_lead_id))
            
            # Remove the temporary lead record
            cursor.execute("DELETE FROM leads WHERE id = ?", (current_lead_id,))
            con.commit()
            return existing_id

        # Update phone number normally if no duplicate exists
        cursor.execute(
            "UPDATE leads SET phone_number = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (clean_phone, current_lead_id)
        )
        con.commit()
        return current_lead_id

    except sqlite3.Error as e:
        print(f"⚠️ Database error during phone update: {e}")
        con.rollback()
        return current_lead_id
    finally:
        con.close()
        
def get_create_lead(phone_number: str):
    con = db_connect()
    cursor = con.cursor()

    # Sanitize phone number before querying or inserting
    clean_phone = format_pk_phone(phone_number)

    cursor.execute(
        "SELECT id FROM leads WHERE phone_number=?", (clean_phone,)
    )
    row = cursor.fetchone()
    if row:
        lead_id = row["id"]
    else:
        cursor.execute(
            "INSERT INTO leads (phone_number) VALUES (?)", (clean_phone,)
        )
        con.commit()
        lead_id = cursor.lastrowid
    con.close()
    return lead_id

def init_db():
    con = db_connect()
    cursor = con.cursor()

    cursor.execute("PRAGMA foreign_keys = ON;")
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
            next_contact_date TEXT,
            lead_stage TEXT DEFAULT 'New Inquiry',
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
            land_area TEXT,
            mouza_location TEXT,
            doc_type TEXT,
            asking_price TEXT,
            status TEXT CHECK(status IN ('AVAILABLE', 'PENDING', 'SOLD')) DEFAULT 'AVAILABLE',
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


def get_history(lead_id: int, limit: int = 12):
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

def mark_property_as_sold(property_id: int) -> bool:
    """
    Updates status to 'SOLD' and deletes the associated image file from disk.
    """
    con = db_connect()
    con.row_factory = sqlite3.Row
    cursor = con.cursor()

    try:
        # Fetch image path before updating status
        cursor.execute("SELECT image_url FROM properties WHERE id = ?", (property_id,))
        row = cursor.fetchone()

        if row and row["image_url"]:
            image_path = row["image_url"]
            # Delete physical image file if it exists
            if os.path.exists(image_path):
                os.remove(image_path)
                print(f"🗑️ Deleted property image: {image_path}")

        # Update property status and clear image reference
        cursor.execute(
            """
            UPDATE properties 
            SET status = 'SOLD', image_url = NULL 
            WHERE id = ?
            """, 
            (property_id,)
        )
        
        con.commit()
        return True
    except Exception as e:
        print(f"❌ Error updating property status: {e}")
        con.rollback()
        return False
    finally:
        con.close()

def delete_sold_property(property_id: int) -> bool:
    """
    Safely purges associated media from storage and removes 
    the sold property record from SQLite.
    """
    # Use timeout to prevent database lock collisions
    con = sqlite3.connect("leads.db", timeout=10)
    con.row_factory = sqlite3.Row
    cursor = con.cursor()

    try:
        # 1. Fetch media path
        cursor.execute("SELECT image_url FROM properties WHERE id = ?", (property_id,))
        row = cursor.fetchone()

        # 2. Delete physical file from disk if present
        if row and row["image_url"]:
            file_path = str(row["image_url"]).strip()
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    print(f"🗑️ Purged media file: {file_path}")
                except Exception as img_err:
                    print(f"⚠️ Could not delete file (might be open elsewhere): {img_err}")

        # 3. Purge record from SQLite
        cursor.execute("DELETE FROM properties WHERE id = ?", (property_id,))
        con.commit()
        return True

    except Exception as e:
        print(f"❌ Error purging property #{property_id}: {e}")
        con.rollback()
        return False
    finally:
        con.close()

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

def parse_number(val_str):
    """Extracts numeric digits from strings like '50 Lac', '1.5 Crore', or '5000000'."""
    if not val_str:
        return None
    cleaned = re.sub(r'[^\d.]', '', str(val_str))
    try:
        return float(cleaned)
    except ValueError:
        return None
def get_buyer_matches(lead_id):
    """
    Compares buyer preferences against active properties in inventory.
    Returns top 3 matching properties with match percentage score.
    """
    conn = db_connect()
    cursor = conn.cursor()

    # 1. Check existing column names in buyer_preferences
    cursor.execute("PRAGMA table_info(buyer_preferences);")
    buyer_cols = [row[1] for row in cursor.fetchall()]

    if not buyer_cols:
        conn.close()
        return []

    # Determine foreign key / primary key column dynamically
    match_col = "lead_id" if "lead_id" in buyer_cols else "id"

    # Build safe query using existing columns
    loc_col = "preferred_location" if "preferred_location" in buyer_cols else "NULL"
    type_col = "property_type" if "property_type" in buyer_cols else "NULL"
    budget_col = "budget_range" if "budget_range" in buyer_cols else "NULL"

    query = f"""
        SELECT {loc_col} AS preferred_location, 
               {type_col} AS property_type, 
               {budget_col} AS budget_range 
        FROM buyer_preferences 
        WHERE {match_col} = ?
    """
    
    try:
        cursor.execute(query, (lead_id,))
        buyer = cursor.fetchone()
    except Exception as e:
        print(f"⚠️ Error fetching buyer preferences: {e}")
        buyer = None

    if not buyer:
        conn.close()
        return []

    pref_loc = (buyer["preferred_location"] or "").lower().strip()
    pref_type = (buyer["property_type"] or "").lower().strip()
    buyer_budget = parse_number(buyer["budget_range"])

    # 2. Check existing column names in properties table
    cursor.execute("PRAGMA table_info(properties);")
    prop_cols = [row[1] for row in cursor.fetchall()]

    p_loc = "location_mouza" if "location_mouza" in prop_cols else ("mouza_location" if "mouza_location" in prop_cols else "NULL")
    p_type = "property_type" if "property_type" in prop_cols else "NULL"
    p_price = "asking_price" if "asking_price" in prop_cols else ("price" if "price" in prop_cols else "NULL")
    p_area = "land_area" if "land_area" in prop_cols else ("land_are" if "land_are" in prop_cols else "NULL")
    p_img = "image_url" if "image_url" in prop_cols else "NULL"

    prop_query = f"""
        SELECT id, title, 
               {p_loc} AS location, 
               {p_type} AS property_type, 
               {p_price} AS price, 
               {p_area} AS area, 
               {p_img} AS image_url 
        FROM properties
    """

    try:
        cursor.execute(prop_query)
        properties = cursor.fetchall()
    except Exception as e:
        print(f"⚠️ Error fetching properties: {e}")
        properties = []
    finally:
        conn.close()

    matches = []
    for prop in properties:
        score = 0
        reasons = []

        prop_loc = (prop["location"] or "").lower().strip()
        prop_type = (prop["property_type"] or "").lower().strip()
        prop_price = parse_number(prop["price"])

        # Location Match (40 Points)
        if pref_loc and prop_loc and (pref_loc in prop_loc or prop_loc in pref_loc):
            score += 40
            reasons.append("Location Match")

        # Property Type Match (35 Points)
        if pref_type and prop_type and (pref_type in prop_type or prop_type in pref_type):
            score += 35
            reasons.append("Property Type Match")

        # Budget Match (25 Points) - Within 15% tolerance
        if buyer_budget and prop_price:
            if prop_price <= buyer_budget * 1.15:
                score += 25
                reasons.append("Within Budget")

        if score > 0:
            matches.append({
                "property_id": prop["id"],
                "title": prop["title"],
                "location": prop["location"],
                "property_type": prop["property_type"],
                "price": prop["price"],
                "area": prop["area"],
                "image_url": prop["image_url"],
                "score": score,
                "reasons": reasons
            })

    matches.sort(key=lambda x: x["score"], reverse=True)
    return matches[:3]

def update_lead_pipeline(lead_id, next_contact_date, lead_stage):
    """Updates the follow-up date and stage for a given lead."""
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE leads 
        SET next_contact_date = ?, lead_stage = ?
        WHERE id = ?
    """, (str(next_contact_date) if next_contact_date else None, lead_stage, lead_id))
    conn.commit()
    conn.close()

def get_leads_due_today():
    """Fetches leads where next_contact_date is today or overdue."""
    today_str = date.today().isoformat()
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, COALESCE(NULLIF(client_name, ''), 'Awaiting Name') AS client_name, 
               phone_number, intent, lead_tag, next_contact_date, COALESCE(lead_stage, 'New Inquiry') AS lead_stage
        FROM leads
        WHERE next_contact_date IS NOT NULL AND next_contact_date <= ?
        ORDER BY next_contact_date ASC
    """, (today_str,))
    due_leads = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return due_leads

if __name__ == "__main__":
    init_db()