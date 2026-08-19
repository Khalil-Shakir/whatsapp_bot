from fastapi import FastAPI
from database import db_connect

app = FastAPI()

@app.get("/leads")
def get_leads():
    conn = db_connect()
    leads = conn.execute("SELECT * FROM leads").fetchall()
    conn.close()
    return [dict(row) for row in leads]

@app.get("/properties")
def get_properties():
    conn = db_connect()
    properties = conn.execute("SELECT * FROM properties").fetchall()
    conn.close()
    return [dict(row) for row in properties]
