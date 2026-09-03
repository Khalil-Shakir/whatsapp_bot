import sqlite3

# Connect to your SQLite database file
conn = sqlite3.connect("leads.db")  # Replace with your actual .db file path
cursor = conn.cursor()

try:
    # Delete all records from the leads table
    cursor.execute("DELETE FROM leads;")

    # Optional: Reset the AUTOINCREMENT primary key counter back to 1
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='leads';")

    conn.commit()
    print("Successfully deleted all records from 'leads' table.")

except sqlite3.Error as e:
    conn.rollback()
    print(f"Error occurred while deleting leads: {e}")

finally:
    conn.close()