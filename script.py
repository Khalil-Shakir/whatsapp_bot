import sqlite3
import re

def clean_existing_db():
    conn = sqlite3.connect("leads.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, phone_number FROM leads")
    rows = cursor.fetchall()
    
    for lead_id, phone in rows:
        digits = re.sub(r'\D', '', str(phone))
        if digits.startswith("03") and len(digits) == 11:
            clean = "92" + digits[1:]
        elif digits.startswith("923") and len(digits) == 12:
            clean = digits
        elif digits.startswith("3") and len(digits) == 10:
            clean = "92" + digits
        else:
            clean = digits
            
        cursor.execute("UPDATE leads SET phone_number = ? WHERE id = ?", (clean, lead_id))
        
    conn.commit()
    conn.close()
    print("✅ Database phone numbers sanitized!")

clean_existing_db()