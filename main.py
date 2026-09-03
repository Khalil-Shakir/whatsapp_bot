import os
import shutil
import sqlite3
import uvicorn
from typing import List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Form, File, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Malik Property API")

# Allow all origins, methods, and headers to prevent CORS blocking
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "leads.db")

# Create static media upload directory
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")


def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes database tables and populates seed data if empty."""
    conn = get_db_connection()
    cursor = conn.cursor()
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
            image TEXT
        )
    """)
    conn.commit()

    # Seed table with initial items if table is brand new/empty
    cursor.execute("SELECT COUNT(*) FROM inventory")
    if cursor.fetchone()[0] == 0:
        seed_data = [
            (
                "1204 Highland Crest",
                "$4,250,000",
                "Villa",
                "Beverly Hills, CA 90210",
                4,
                3,
                3500,
                "AVAILABLE",
                "Oct 12, 2023",
                "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=600&auto=format&fit=crop",
            ),
            (
                "Tech Hub Suite 4B",
                "$1,850,000",
                "Commercial",
                "Downtown Metro, NY 10001",
                0,
                2,
                1800,
                "PENDING",
                "Sep 28, 2023",
                "https://images.unsplash.com/photo-1497366216548-37526070297c?w=600&auto=format&fit=crop",
            ),
            (
                "88 Maplewood Drive",
                "$945,000",
                "House",
                "Oak Park, IL 60302",
                3,
                2,
                2200,
                "SOLD",
                "Nov 01, 2023",
                "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?w=600&auto=format&fit=crop",
            ),
        ]
        cursor.executemany(
            """
            INSERT INTO inventory (title, price, type, location, beds, baths, sqft, status, date_added, image)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            seed_data,
        )
        conn.commit()

    conn.close()


# Initialize database schemas on backend startup
init_db()


# WebSocket Connection Manager Class
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print("⚡ WebSocket client connected")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print("🔌 WebSocket client disconnected")

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Broadcast error: {e}")
                self.disconnect(connection)


manager = ConnectionManager()


# Inventory Pydantic Schema
class PropertyItem(BaseModel):
    id: Optional[int] = None
    title: str
    price: str
    type: str
    location: str
    beds: Optional[int] = 0
    baths: Optional[int] = 0
    sqft: Optional[int] = 0
    status: str = "AVAILABLE"
    dateAdded: str
    image: Optional[str] = (
        "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=600&auto=format&fit=crop"
    )


@app.get("/")
def read_root():
    return {"status": "FastAPI operational", "db_path": DB_PATH}


@app.get("/api/inventory", response_model=List[PropertyItem])
async def get_inventory():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM inventory ORDER BY id DESC")
        rows = cursor.fetchall()
        conn.close()

        items = []
        for r in rows:
            items.append(
                {
                    "id": r["id"],
                    "title": r["title"],
                    "price": r["price"],
                    "type": r["type"],
                    "location": r["location"],
                    "beds": r["beds"],
                    "baths": r["baths"],
                    "sqft": r["sqft"],
                    "status": r["status"],
                    "dateAdded": r["date_added"],
                    "image": r["image"],
                }
            )
        return items
    except Exception as e:
        print(f"❌ Error during /api/inventory GET: {str(e)}")
        return []


@app.post("/api/inventory")
async def create_property(
    title: str = Form(...),
    price: str = Form(...),
    type: str = Form(...),
    location: str = Form(...),
    beds: int = Form(0),
    baths: int = Form(0),
    sqft: int = Form(0),
    status: str = Form("AVAILABLE"),
    dateAdded: str = Form(...),
    file: Optional[UploadFile] = File(None),
):
    image_url = (
        "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=600&auto=format&fit=crop"
    )

    if file:
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        image_url = f"http://127.0.0.1:8000/static/uploads/{file.filename}"

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO inventory (title, price, type, location, beds, baths, sqft, status, date_added, image)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                title,
                price,
                type,
                location,
                beds,
                baths,
                sqft,
                status,
                dateAdded,
                image_url,
            ),
        )
        item_id = cursor.lastrowid
        conn.commit()
        conn.close()

        item = {
            "id": item_id,
            "title": title,
            "price": price,
            "type": type,
            "location": location,
            "beds": beds,
            "baths": baths,
            "sqft": sqft,
            "status": status,
            "dateAdded": dateAdded,
            "image": image_url,
        }

        await manager.broadcast({"event": "INVENTORY_UPDATED", "item": item})
        return item
    except Exception as e:
        print(f"❌ Error saving to inventory database: {str(e)}")
        return {"error": "Failed to add inventory item"}


@app.get("/api/dashboard/overview")
def get_dashboard_overview():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM leads")
        total = cursor.fetchone()[0] or 0

        cursor.execute(
            "SELECT COUNT(*) FROM leads WHERE UPPER(COALESCE(intent, '')) LIKE '%BUY%'"
        )
        buyers = cursor.fetchone()[0] or 0

        cursor.execute(
            "SELECT COUNT(*) FROM leads WHERE UPPER(COALESCE(intent, '')) LIKE '%SELL%'"
        )
        sellers = cursor.fetchone()[0] or 0

        cursor.execute("""
            SELECT id, name, phone_number, intent, property_type, COALESCE(budget_min, 0) as budget, last_interaction 
            FROM leads 
            ORDER BY id DESC LIMIT 5
        """)
        rows = cursor.fetchall()
        conn.close()

        hot_leads = []
        for r in rows:
            hot_leads.append(
                {
                    "id": r["id"],
                    "name": r["name"] or r["phone_number"] or "Lead",
                    "phone_number": r["phone_number"] or "N/A",
                    "intent": (r["intent"] or "AWAITING INFO").upper(),
                    "property_type": r["property_type"] or "Property",
                    "budget": f"PKR {r['budget']}",
                    "last_interaction": r["last_interaction"] or "Recently",
                }
            )

        return {
            "total_leads": total,
            "active_chats": total,
            "property_matches": total * 2,
            "conversion_rate": 100 if total > 0 else 0,
            "buyers_count": buyers,
            "sellers_count": sellers,
            "hot_leads": hot_leads,
        }
    except Exception as e:
        print(f"❌ Error during /api/dashboard/overview: {str(e)}")
        return {
            "total_leads": 0,
            "active_chats": 0,
            "property_matches": 0,
            "conversion_rate": 0,
            "buyers_count": 0,
            "sellers_count": 0,
            "hot_leads": [],
            "error": str(e),
        }


@app.get("/api/leads")
def get_all_leads():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM leads ORDER BY id DESC")
        rows = cursor.fetchall()
        conn.close()

        leads_list = []
        for row in rows:
            leads_list.append(
                {
                    "id": row["id"],
                    "name": row["name"] or row["phone_number"] or "New Lead",
                    "phone": row["phone_number"] or "N/A",
                    "intent": (row["intent"] or "AWAITING INFO").upper(),
                    "propertyType": row["property_type"] or "N/A",
                    "budget": f"PKR {row['budget_min'] or 0}",
                    "status": (row["status"] or "NEW").upper(),
                    "addedTime": row["last_interaction"] or "Just now",
                }
            )
        return leads_list
    except Exception as e:
        print(f"❌ Error during /api/leads: {str(e)}")
        return []


class BotNotification(BaseModel):
    phone_number: str
    name: Optional[str] = None
    intent: Optional[str] = None
    message_text: Optional[str] = None


@app.post("/api/internal/broadcast-lead")
async def broadcast_lead(data: BotNotification):
    # Broadcast BOT_MESSAGE event with complete details to connected frontend clients
    await manager.broadcast({
        "event": "BOT_MESSAGE",
        "name": data.name or data.phone_number or "Client",
        "message_text": data.message_text or "Sent a message",
        "intent": data.intent or "AWAITING INFO",
        "phone_number": data.phone_number,
    })

    return {"status": "ok"}


@app.websocket("/ws/activity")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"pong: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"❌ WS Handler Error: {e}")
        manager.disconnect(websocket)

#Auto match#
@app.get("/api/property-matches")
def get_property_matches():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch leads (broad query without strict filtering)
        cursor.execute("""
            SELECT id, name, phone_number, intent, property_type, budget_min, location, last_interaction, status
            FROM leads 
            WHERE intent IS NOT NULL AND TRIM(intent) != ''
            ORDER BY id DESC
        """)
        lead_rows = cursor.fetchall()

        # Fetch all inventory rows
        cursor.execute("SELECT * FROM inventory")
        inventory_rows = cursor.fetchall()
        conn.close()

        # If either database table is empty, return empty list
        if not lead_rows or not inventory_rows:
            return []

        pairs = []
        pair_id = 1

        for lead in lead_rows:
            lead_intent = (lead["intent"] or "").upper()
            
            # Skip leads that are explicitly sellers
            if "SELL" in lead_intent and "BUY" not in lead_intent:
                continue

            lead_budget = lead["budget_min"] or 0
            lead_type = (lead["property_type"] or "").strip().upper()
            lead_loc = (lead["location"] or "").strip().upper()
            lead_name = lead["name"] or lead["phone_number"] or "Valued Lead"

            name_parts = lead_name.split()
            initials = "".join([p[0].upper() for p in name_parts[:2]]) if name_parts else "VL"

            for prop in inventory_rows:
                score = 70  # Base match score for available buyer & property pair

                prop_type = (prop["type"] or "").strip().upper()
                prop_loc = (prop["location"] or "").strip().upper()

                # Clean numeric price conversion for Pakistani Crore / Lakh strings or raw numbers
                price_raw = str(prop["price"]).upper().replace(",", "").replace("$", "").replace("PKR", "").strip()
                prop_price = 0
                
                if "CRORE" in price_raw or "CR" in price_raw:
                    num_part = price_raw.replace("CRORE", "").replace("CR", "").strip()
                    try:
                        prop_price = float(num_part) * 10000000
                    except ValueError:
                        pass
                elif "LAKH" in price_raw or "LACS" in price_raw:
                    num_part = price_raw.replace("LAKH", "").replace("LACS", "").strip()
                    try:
                        prop_price = float(num_part) * 100000
                    except ValueError:
                        pass
                else:
                    try:
                        prop_price = float(price_raw)
                    except ValueError:
                        prop_price = 0

                # Match scoring bonuses
                if lead_type and prop_type and (lead_type in prop_type or prop_type in lead_type):
                    score += 15

                if lead_loc and prop_loc and (lead_loc in prop_loc or prop_loc in lead_loc):
                    score += 10

                if lead_budget > 0 and prop_price > 0:
                    if prop_price <= lead_budget * 1.25:
                        score += 10

                score = min(score, 98)

                pairs.append({
                    "id": pair_id,
                    "matchScore": score,
                    "lead": {
                        "id": lead["id"],
                        "name": lead_name,
                        "initials": initials,
                        "source": "WhatsApp Bot",
                        "status": (lead["status"] or "HOT LEAD").upper(),
                        "lastActive": lead["last_interaction"] or "Recently",
                        "budget": f"PKR {lead_budget:,}" if lead_budget else "Flexible",
                        "type": lead["property_type"] or "Plot / Property",
                        "location": lead["location"] or "Mianwali"
                    },
                    "property": {
                        "id": prop["id"],
                        "title": prop["title"],
                        "price": str(prop["price"]),
                        "image": prop["image"] or "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=600&auto=format&fit=crop",
                        "beds": prop["beds"] or 0,
                        "baths": prop["baths"] or 0,
                        "sqft": prop["sqft"] or 0,
                        "tag": "Top Match" if score >= 85 else "Recommended"
                    }
                })
                pair_id += 1

        pairs.sort(key=lambda x: x["matchScore"], reverse=True)
        return pairs

    except Exception as e:
        print(f"❌ Error during /api/property-matches GET: {str(e)}")
        return []
        
class ProposalRequest(BaseModel):
    pair_id: int

@app.post("/api/property-matches/send-proposal")
async def send_property_proposal(data: ProposalRequest):
    # Hook into your notification system or WhatsApp automated dispatcher here
    await manager.broadcast({"event": "PROPOSAL_SENT", "pair_id": data.pair_id})
    return {"status": "success", "message": "Proposal dispatched successfully to lead."}

@app.get("/api/dashboard/bot-activities")
def get_recent_bot_activities():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Query the latest 5 activities directly from SQLite leads table
        cursor.execute("""
            SELECT id, name, phone_number, intent, property_type, last_interaction 
            FROM leads 
            ORDER BY id DESC 
            LIMIT 5
        """)
        rows = cursor.fetchall()
        conn.close()

        activities = []
        for r in rows:
            lead_name = r["name"] or r["phone_number"] or "Lead"
            intent = (r["intent"] or "").upper()
            prop_type = r["property_type"] or "property"
            time_str = r["last_interaction"] or "Just now"

            if "BUY" in intent:
                text = "Bot captured buyer inquiry from"
                target = f"for {prop_type}"
            elif "SELL" in intent:
                text = "Bot registered seller listing from"
                target = f"for {prop_type}"
            else:
                text = "Bot logged active conversation with"
                target = f"regarding {prop_type}"

            activities.append(
                {
                    "id": f"db_{r['id']}",
                    "type": "BOT_RESPONSE",
                    "text": text,
                    "highlightText": lead_name,
                    "targetText": target,
                    "time": time_str,
                }
            )

        return activities
    except Exception as e:
        print(f"❌ Error fetching bot activities: {str(e)}")
        return []@app.get("/api/dashboard/bot-activities")
def get_recent_bot_activities():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Query the latest 5 activities directly from SQLite leads table
        cursor.execute("""
            SELECT id, name, phone_number, intent, property_type, last_interaction 
            FROM leads 
            ORDER BY id DESC 
            LIMIT 5
        """)
        rows = cursor.fetchall()
        conn.close()

        activities = []
        for r in rows:
            lead_name = r["name"] or r["phone_number"] or "Lead"
            intent = (r["intent"] or "").upper()
            prop_type = r["property_type"] or "property"
            time_str = r["last_interaction"] or "Just now"

            if "BUY" in intent:
                text = "Bot captured buyer inquiry from"
                target = f"for {prop_type}"
            elif "SELL" in intent:
                text = "Bot registered seller listing from"
                target = f"for {prop_type}"
            else:
                text = "Bot logged active conversation with"
                target = f"regarding {prop_type}"

            activities.append(
                {
                    "id": f"db_{r['id']}",
                    "type": "BOT_RESPONSE",
                    "text": text,
                    "highlightText": lead_name,
                    "targetText": target,
                    "time": time_str,
                }
            )

        return activities
    except Exception as e:
        print(f"❌ Error fetching bot activities: {str(e)}")
        return []



if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)