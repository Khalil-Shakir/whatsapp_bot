import os, re, math
import shutil
import logging
import sqlite3
import uvicorn
from typing import List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Form, File, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import json, asyncio, qrcode, io, base64, time
from neonize.client import NewClient
from neonize.events import ConnectedEv, DisconnectedEv, MessageEv, LoggedOutEv
from contextlib import asynccontextmanager
from typing import Dict, Any, List
from groq import Groq
from fastapi import HTTPException

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot_manager")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "leads.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

client = NewClient("auth_info.db")

# Helper function to trigger client re-connection in executor thread
def reconnect_client():
    try:
        logger.info("Attempting automatic re-connection to trigger QR generation...")
        client.connect()
    except Exception as e:
        logger.error(f"Error during client reconnection: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    loop.run_in_executor(None, client.connect)
    yield

app = FastAPI(title="Malik Property Automation API", lifespan=lifespan)

class UpdateStatusPayload(BaseModel):
    status: str

class ToggleBotPayload(BaseModel):
    enabled: bool

class UpdateInventoryStatusPayload(BaseModel):
    status: str
class UpdateAreaPayload(BaseModel):
    area: str

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

@app.patch("/api/leads/{lead_id}/status")
async def update_lead_status(lead_id: int, payload: UpdateStatusPayload):
    valid_statuses = ["NEW", "FOLLOW UP", "CLOSED"]
    new_status = payload.status.upper()
    
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Invalid status value")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE leads SET status = ? WHERE id = ?", (new_status, lead_id))
    conn.commit()
    
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Lead not found")
        
    conn.close()

    await state_manager.add_activity({
        "type": "action",
        "text": f"Lead #{lead_id} status updated to",
        "highlightText": new_status,
        "time": "JUST NOW"
    })

    return {"status": "success", "lead_id": lead_id, "new_status": new_status}

@app.patch("/api/leads/{lead_id}/area")
async def update_lead_area(lead_id: int, payload: UpdateAreaPayload):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE leads SET area = ? WHERE id = ?", (payload.area, lead_id))
    conn.commit()

    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Lead not found")

    conn.close()

    await state_manager.add_activity({
        "type": "action",
        "text": f"Lead #{lead_id} required area updated to",
        "highlightText": payload.area,
        "time": "JUST NOW"
    })

    return {"status": "success", "lead_id": lead_id, "new_area": payload.area}

@app.patch("/api/leads/{lead_id}/toggle-bot")
async def toggle_lead_bot(lead_id: int, payload: ToggleBotPayload):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE leads SET bot_enabled = ? WHERE id = ?", (1 if payload.enabled else 0, lead_id))
    conn.commit()
    
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Lead not found")
        
    conn.close()

    await state_manager.add_activity({
        "type": "action",
        "text": f"Bot {'enabled' if payload.enabled else 'disabled'} for Lead #{lead_id}",
        "highlightText": "STATUS UPDATE",
        "time": "JUST NOW"
    })

    return {"status": "success", "lead_id": lead_id, "bot_enabled": payload.enabled}

@app.patch("/api/inventory/{item_id}/status")
async def update_inventory_item_status(item_id: int, payload: UpdateInventoryStatusPayload):
    valid_statuses = ["AVAILABLE", "PENDING", "SOLD"]
    new_status = payload.status.upper()

    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Invalid status value")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE inventory SET status = ? WHERE id = ?", (new_status, item_id))
    conn.commit()

    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Inventory item not found")

    cursor.execute("SELECT * FROM inventory WHERE id = ?", (item_id,))
    updated_item_row = cursor.fetchone()
    conn.close()

    await state_manager.add_activity({
        "type": "action",
        "text": f"Property listing #{item_id} status updated to",
        "highlightText": new_status,
        "time": "JUST NOW"
    })

    return {"status": "success", "item_id": item_id, "new_status": new_status}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

class BotStateManager:
    def __init__(self):
        self.status: str = "DISCONNECTED"
        self.qr_code_base64: Optional[str] = None
        self.recent_activities: List[dict] = []
        self.active_websockets: List[WebSocket] = []

    async def connect_ws(self, websocket: WebSocket):
        await websocket.accept()
        self.active_websockets.append(websocket)
        logger.info("Dashboard connected to websocket")
        await websocket.send_text(json.dumps(self.get_state_payload()))

    def disconnect_ws(self, websocket: WebSocket):
        if websocket in self.active_websockets:
            self.active_websockets.remove(websocket)
            logger.info("Dashboard disconnected from websocket")

    def get_state_payload(self) -> dict:
        return {
            "type": "STATE_UPDATE",
            "status": self.status,
            "qr_code": self.qr_code_base64,
            "activities": self.recent_activities
        }

    async def broadcast(self, data: dict):
        for connection in list(self.active_websockets):
            try:
                await connection.send_text(json.dumps(data))
            except Exception as e:
                logger.info(f"Error broadcasting to client: {e}")

    async def add_activity(self, activity: dict):
        if "id" not in activity or not activity["id"]:
            activity["id"] = f"act-{time.time_ns()}"

        is_duplicate = any(
            a.get("id") == activity.get("id") or 
            (a.get("text") == activity.get("text") and a.get("targetText") == activity.get("targetText"))
            for a in self.recent_activities[:5]
        )

        if is_duplicate:
            return

        self.recent_activities.insert(0, activity)
        if len(self.recent_activities) > 20:
            self.recent_activities.pop()

        payload = {
            "type": "NEW_ACTIVITY",
            "activity": activity
        }
        await self.broadcast(payload)

    async def update_status(self, new_status: str, qr_base64: Optional[str] = None):
        self.status = new_status
        self.qr_code_base64 = qr_base64
        payload = self.get_state_payload()
        await self.broadcast(payload)

state_manager = BotStateManager()

try:
    loop = asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

@client.qr
def on_qr(client_instance, qr_bytes: bytes):
    qr_str = qr_bytes.decode("utf-8") if isinstance(qr_bytes, bytes) else str(qr_bytes)
    qr_img = qrcode.make(qr_str)
    buffered = io.BytesIO()
    qr_img.save(buffered, format="PNG")
    base64_qr = "data:image/png;base64," + base64.b64encode(buffered.getvalue()).decode("utf-8")

    asyncio.run_coroutine_threadsafe(
        state_manager.update_status("NEEDS_QR", base64_qr),
        loop
    )

@client.event(ConnectedEv)
def on_connected(client_instance, event: ConnectedEv):
    logger.info("WhatsApp bot connected successfully!")
    asyncio.run_coroutine_threadsafe(
        state_manager.update_status("CONNECTED", None),
        loop
    )

@client.event(DisconnectedEv)
def on_disconnected(client_instance, event: DisconnectedEv):
    logger.warning("WhatsApp bot disconnected! Triggering automatic reconnect...")
    asyncio.run_coroutine_threadsafe(
        state_manager.update_status("DISCONNECTED", None),
        loop
    )
    # Automatically schedule a reconnection attempt to generate a new QR code
    loop.run_in_executor(None, reconnect_client)

@client.event(LoggedOutEv)
def on_logged_out(client_instance, event: LoggedOutEv):
    logger.warning("WhatsApp logged out from mobile! Triggering fresh session reconnect...")
    asyncio.run_coroutine_threadsafe(
        state_manager.update_status("DISCONNECTED", None),
        loop
    )
    loop.run_in_executor(None, reconnect_client)

@app.websocket("/ws/bot-status")
async def websocket_endpoint(websocket: WebSocket):
    await state_manager.connect_ws(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        state_manager.disconnect_ws(websocket)

def init_db():
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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone_number TEXT UNIQUE,
            phone TEXT,
            intent TEXT,
            property_type TEXT,
            budget_min REAL,
            budget_max REAL,
            budget TEXT,
            area TEXT,
            location TEXT,
            status TEXT DEFAULT 'NEW',
            bot_enabled INTEGER DEFAULT 1,
            last_interaction TEXT,
            added_time TEXT
        )
    """)
    # New table for chat history memory
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            sender TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM inventory")
    if cursor.fetchone()[0] == 0:
        seed_data = [
            ("1204 Highland Crest", "$4,250,000", "Villa", "Beverly Hills, CA 90210", 4, 3, 3500, "AVAILABLE", "Oct 12, 2023", "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=600&auto=format&fit=crop"),
            ("Tech Hub Suite 4B", "$1,850,000", "Commercial", "Downtown Metro, NY 10001", 0, 2, 1800, "PENDING", "Sep 28, 2023", "https://images.unsplash.com/photo-1497366216548-37526070297c?w=600&auto=format&fit=crop"),
            ("88 Maplewood Drive", "$945,000", "House", "Oak Park, IL 60302", 3, 2, 2200, "SOLD", "Nov 01, 2023", "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?w=600&auto=format&fit=crop"),
        ]
        cursor.executemany("""
            INSERT INTO inventory (title, price, type, location, beds, baths, sqft, status, date_added, image)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, seed_data)
        conn.commit()

    conn.close()

init_db()

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
    image: Optional[str] = "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=600&auto=format&fit=crop"

@app.get("/")
def read_root():
    return {"status": "FastAPI operational", "db_path": DB_PATH}

@app.get("/api/dashboard/overview")
def get_dashboard_overview():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Total Leads
        cursor.execute("SELECT COUNT(*) FROM leads")
        total_leads = cursor.fetchone()[0] or 0

        # 2. Real-time Active Chats (Leads with activity in the last 24 hours)
        cursor.execute("""
            SELECT COUNT(*) FROM leads 
            WHERE last_interaction >= datetime('now', '-1 day')
        """)
        active_chats = cursor.fetchone()[0] or 0

        # 3. Buyers & Sellers breakdown
        cursor.execute("SELECT COUNT(*) FROM leads WHERE UPPER(intent) = 'BUYING'")
        buyers_count = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(*) FROM leads WHERE UPPER(intent) = 'SELLING'")
        sellers_count = cursor.fetchone()[0] or 0

        # 4. Property Matches
        cursor.execute("""
            SELECT COUNT(*) FROM leads 
            WHERE property_type IS NOT NULL AND property_type != ''
        """)
        property_matches = cursor.fetchone()[0] or 0

        # 5. Conversion Rate
        cursor.execute("""
            SELECT COUNT(*) FROM leads 
            WHERE UPPER(status) IN ('HOT LEAD', 'CLOSED')
        """)
        converted_leads = cursor.fetchone()[0] or 0
        conversion_rate = round((converted_leads / total_leads * 100), 1) if total_leads > 0 else 0

        # 6. Hot Leads List
        cursor.execute("SELECT * FROM leads WHERE UPPER(status) = 'HOT LEAD' ORDER BY id DESC LIMIT 5")
        hot_leads_rows = cursor.fetchall()
        conn.close()

        hot_leads = [
            {
                "id": r["id"],
                "name": r["name"] or "Unknown",
                "phone_number": r["phone_number"] if "phone_number" in r.keys() else r.get("phone", ""),
                "budget": f"PKR {r['budget_min']}" if "budget_min" in r.keys() and r["budget_min"] else r.get("budget", "N/A"),
                "intent": (r["intent"] or "BUYING").upper(),
                "last_interaction": r.get("last_interaction") or r.get("added_time") or "Recently"
            }
            for r in hot_leads_rows
        ]

        return {
            "total_leads": total_leads,
            "active_chats": active_chats,
            "property_matches": property_matches,
            "conversion_rate": conversion_rate,
            "total_leads_change": 0,
            "active_chats_change": 0,
            "property_matches_change": 0,
            "conversion_rate_change": 0,
            "buyers_count": buyers_count,
            "sellers_count": sellers_count,
            "hot_leads": hot_leads
        }
    except Exception as e:
        logger.error(f"Error fetching dashboard overview: {e}")
        return {
            "total_leads": 0,
            "active_chats": 0,
            "property_matches": 0,
            "conversion_rate": 0,
            "total_leads_change": 0,
            "active_chats_change": 0,
            "property_matches_change": 0,
            "conversion_rate_change": 0,
            "buyers_count": 0,
            "sellers_count": 0,
            "hot_leads": []
        }

@app.get("/api/dashboard/bot-activities")
async def get_bot_activities():
    return state_manager.recent_activities

def parse_price(price_str: str) -> float:
    """Helper function to parse numeric values from price strings."""
    if not price_str:
        return 0.0
    cleaned = re.sub(r"[^\d.]", "", str(price_str))
    try:
        return float(cleaned)
    except ValueError:
        return 0.0

@app.get("/api/property-matches")
async def get_property_matches():
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Exclude leads with a CLOSED status from the matching pipeline
        cursor.execute("SELECT * FROM leads WHERE UPPER(COALESCE(status, 'NEW')) != 'CLOSED' ORDER BY id DESC")
        raw_leads = [dict(row) for row in cursor.fetchall()]

        cursor.execute("SELECT * FROM inventory WHERE UPPER(status) = 'AVAILABLE'")
        raw_inventory = [dict(row) for row in cursor.fetchall()]

        conn.close()

        matches = []

        for lead in raw_leads:
            lead_id = lead.get("id")
            lead_name = (
                lead.get("name")
                or lead.get("phone_number")
                or lead.get("phone")
                or f"Lead #{lead_id}"
            )
            lead_phone = lead.get("phone_number") or lead.get("phone") or "N/A"
            lead_type = (lead.get("property_type") or "").strip().lower()
            lead_intent = (lead.get("intent") or "Buying").strip().upper()
            
            b_min = lead.get("budget_min")
            b_max = lead.get("budget_max")
            fallback_budget = lead.get("budget")

            best_match = None
            highest_score = 0

            for prop in raw_inventory:
                prop_type = (prop.get("type") or "").strip().lower()
                prop_price_val = parse_price(prop.get("price"))

                score = 50

                if lead_type and prop_type:
                    if lead_type in prop_type or prop_type in lead_type:
                        score += 25

                if b_min is not None or b_max is not None:
                    min_val = b_min if b_min is not None else 0
                    max_val = b_max if b_max is not None else float("inf")
                    if min_val <= prop_price_val <= max_val:
                        score += 20
                    elif prop_price_val < min_val:
                        score += 10
                elif fallback_budget:
                    budget_val = parse_price(fallback_budget)
                    if budget_val > 0 and abs(budget_val - prop_price_val) <= (budget_val * 0.2):
                        score += 20

                if score > highest_score:
                    highest_score = score
                    best_match = prop

            if best_match and highest_score >= 60:
                matches.append({
                    "id": f"match-{lead_id}-{best_match.get('id')}",
                    "matchScore": highest_score,
                    "lead": {
                        "id": lead_id,
                        "name": lead_name,
                        "phone": lead_phone,
                        "initials": lead_name[:2].upper() if lead_name else "LD",
                        "intent": lead_intent,
                        "source": "WhatsApp Bot",
                        "lastActive": lead.get("last_interaction") or lead.get("added_time") or "Recently",
                        "budget": (
                            f"PKR {b_min:,.0f} - {b_max:,.0f}" if b_min and b_max 
                            else (fallback_budget or "Not Specified")
                        ),
                        "type": lead.get("property_type") or "Any",
                        "location": lead.get("location") or "Mianwali",
                        "status": lead.get("status") or "NEW"
                    },
                    "property": {
                        "id": best_match.get("id"),
                        "title": best_match.get("title") or "Database Property",
                        "price": best_match.get("price") or "Contact Agent",
                        "image": best_match.get("image") or "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=600&auto=format&fit=crop",
                        "beds": best_match.get("beds") or 0,
                        "baths": best_match.get("baths") or 0,
                        "sqft": best_match.get("sqft") or 0,
                        "tag": best_match.get("type") or "Property"
                    }
                })

        matches.sort(key=lambda x: x["matchScore"], reverse=True)
        return matches

    except Exception as e:
        logger.error(f"Failed to calculate property matches: {str(e)}")
        return []
class ProposalRequest(BaseModel):
    lead_id: int
    phone: str
    property_id: int
    property_title: str
    price: str

@app.post("/api/send-proposal")
async def send_proposal(req: ProposalRequest):
    try:
        message = (
            f"Hello! We found a property matching your requirements:\n\n"
            f"🏠 *{req.property_title}*\n"
            f"💰 Price: {req.price}\n\n"
            f"Let us know if you would like to schedule a visit or receive more details!"
        )
        logger.info(f"Sending proposal to {req.phone} for Property ID {req.property_id}")
        return {"status": "success", "message": "Proposal dispatched successfully."}
    except Exception as e:
        logger.error(f"Error sending proposal: {str(e)}")
        raise HTTPException(status_code=500, detail="Proposal dispatch failed.")
    
@app.get("/api/inventory", response_model=Dict[str, Any])
async def get_inventory(page: int = 1, limit: int = 6):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        offset = (page-1)*limit
        total_items = cursor.execute("SELECT COUNT(*) FROM inventory").fetchone()[0]
        total_pages = math.ceil(total_items / limit)
        cursor.execute("SELECT * FROM inventory ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset))
        rows = cursor.fetchall()
        conn.close()

        items = [
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
            for r in rows
        ]
        return {
            "items": items,
            "total_items": total_items,
            "page": page,
            "limit": limit,
            "total_pages": total_pages
        }
    except Exception as e:
        logger.error(f"Error in GET /api/inventory: {e}")
        return {"items":[], "total_items": 0, "page":1, "limit":limit, "total_pages":1}

@app.delete("/api/inventory/{item_id}")
async def delete_inventory_item(item_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM inventory WHERE id = ?", (item_id,))
    conn.commit()
    
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Inventory item not found")
        
    conn.close()

    await state_manager.add_activity({
        "type": "action",
        "text": f"Property listing #{item_id} deleted",
        "highlightText": "DELETED",
        "time": "JUST NOW"
    })

    return {"status": "success", "item_id": item_id}
@app.post("/api/inventory")
async def create_property(
    title: str = Form(...),
    price: Optional[str] = Form(""),
    type: str = Form(...),
    location: str = Form(...),
    # UPGRADE: Use Optional[Any] or string types for number fields 
    # so empty form fields from the frontend don't trigger a 422 error.
    beds: Optional[Any] = Form(0),
    baths: Optional[Any] = Form(0),
    sqft: Optional[Any] = Form(0),
    status: str = Form("AVAILABLE"),
    dateAdded: Optional[str] = Form(""),
    price_per_marla: Optional[Any] = Form(0.0),
    marlas: Optional[Any] = Form(0.0),
    file: Optional[UploadFile] = File(None),
):
    # Safely parse numbers to prevent type conversion errors
    try:
        beds_val = int(beds) if beds not in [None, ""] else 0
        baths_val = int(baths) if baths not in [None, ""] else 0
        sqft_val = int(sqft) if sqft not in [None, ""] else 0
        ppm_val = float(price_per_marla) if price_per_marla not in [None, ""] else 0.0
        marlas_val = float(marlas) if marlas not in [None, ""] else 0.0
    except ValueError:
        beds_val, baths_val, sqft_val, ppm_val, marlas_val = 0, 0, 0, 0.0, 0.0

    total_calculated_price = ppm_val * marlas_val
    final_price = price if price else (f"PKR {total_calculated_price:,.0f}" if total_calculated_price > 0 else "Contact Agent")
    
    final_date = dateAdded if dateAdded else datetime.now().strftime("%b %d, %Y")
    image_url = "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=600&auto=format&fit=crop"

    if file and file.filename:
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        image_url = f"http://127.0.0.1:8000/static/uploads/{file.filename}"

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # UPGRADE: Fixed SQL placeholder count. 
        # Exactly 12 placeholders matching your 12 columns and parameters!
        cursor.execute(
            """
            INSERT INTO inventory (title, price, type, location, beds, baths, sqft, status, date_added, image, price_per_marla, marlas)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (title, final_price, type, location, beds_val, baths_val, sqft_val, status, final_date, image_url, ppm_val, marlas_val),
        )
        item_id = cursor.lastrowid
        conn.commit()
        conn.close()

        item = {
            "id": item_id,
            "title": title,
            "price": final_price,
            "type": type,
            "location": location,
            "beds": beds_val,
            "baths": baths_val,
            "sqft": sqft_val,
            "status": status,
            "dateAdded": final_date,
            "image": image_url,
        }
        await state_manager.broadcast({"event": "INVENTORY_UPDATED", "item": item})
        return item
    except Exception as e:
        logger.error(f"Error saving to inventory: {e}")
        return {"error": "Failed to add inventory item"}

@app.get("/api/leads")
async def get_leads():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM leads ORDER BY id DESC")
        rows = cursor.fetchall()
        conn.close()

        leads = []
        for r in rows:
            keys = r.keys()

            phone = (
                r["phone_number"]
                if "phone_number" in keys and r["phone_number"]
                else (r["phone"] if "phone" in keys else "N/A")
            )

            if "budget_min" in keys and r["budget_min"] is not None:
                budget = f"PKR {r['budget_min']:,.0f}"
                if (
                    "budget_max" in keys
                    and r["budget_max"] is not None
                    and r["budget_max"] != r["budget_min"]
                ):
                    budget += f" - {r['budget_max']:,.0f}"
            else:
                budget = r["budget"] if "budget" in keys and r["budget"] else "N/A"

            added_time = (
                r["last_interaction"]
                if "last_interaction" in keys and r["last_interaction"]
                else (
                    r["added_time"]
                    if "added_time" in keys and r["added_time"]
                    else "Recently"
                )
            )

            leads.append(
                {
                    "id": r["id"],
                    "name": r["name"] or phone or "Unknown",
                    "phone": phone,
                    "intent": (r["intent"] or "AWAITING INFO").upper(),
                    "propertyType": r["property_type"] or "N/A",
                    "budget": budget,
                    "area": r["area"] if "area" in keys and r["area"] else "N/A",
                    "location": r["location"] if "location" in keys and r["location"] else "N/A",
                    "status": (r["status"] or "NEW").upper(),
                    "botEnabled": bool(r["bot_enabled"]) if "bot_enabled" in keys and r["bot_enabled"] is not None else True,
                    "addedTime": added_time,
                }
            )

        return leads
    except Exception as e:
        logger.error(f"Error fetching leads: {e}")
        return []

# Bot functionality
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

def format_pk_phone(phone_user: str) -> str:
    digits = "".join(filter(str.isdigit, str(phone_user)))
    if digits.startswith("92") and len(digits) == 12:
        return "0" + digits[2:]
    return digits

def get_create_lead(phone: str) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO leads (phone_number, intent, status, last_interaction)
        VALUES (?, 'AWAITING INFO', 'NEW', datetime('now'))
        ON CONFLICT(phone_number) DO UPDATE SET last_interaction=datetime('now')
        """,
        (phone,),
    )
    conn.commit()
    cursor.execute("SELECT id FROM leads WHERE phone_number = ?", (phone,))
    lead_id = cursor.fetchone()[0]
    conn.close()
    return lead_id

def get_lead_state(lead_id: int) -> dict:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT phone_number, name, intent, property_type, budget_min, budget_max, area, location, status 
        FROM leads WHERE id = ?
        """,
        (lead_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else {}

def sanitize_intent(intent_str: str) -> str:
    valid_intents = ["BUYING", "SELLING", "RENT"]
    return intent_str if intent_str in valid_intents else "AWAITING INFO"

def update_lead(
    lead_id: int,
    name: str = None,
    intent: str = None,
    property_type: str = None,
    budget_min: float = None,
    budget_max: float = None,
    area: str = None,
    location: str = None,
    status: str = None,
):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE leads 
        SET name = COALESCE(?, name),
            intent = COALESCE(?, intent),
            property_type = COALESCE(?, property_type),
            budget_min = COALESCE(?, budget_min),
            budget_max = COALESCE(?, budget_max),
            area = COALESCE(?, area),
            location = COALESCE(?, location),
            status = COALESCE(?, status),
            last_interaction = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (name, intent, property_type, budget_min, budget_max, area, location, status, lead_id),
    )
    conn.commit()
    conn.close()

def is_bot_enabled_for_lead(lead_id: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT bot_enabled FROM leads WHERE id = ?", (lead_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row and row["bot_enabled"] is not None:
        return bool(row["bot_enabled"])
    return True

# Helper functions for Chat Memory
def save_chat_message(lead_id: int, sender: str, message: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chat_history (lead_id, sender, message) VALUES (?, ?, ?)",
        (lead_id, sender, message),
    )
    conn.commit()
    conn.close()

def get_chat_history(lead_id: int, limit: int = 10) -> list:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT sender, message FROM chat_history WHERE lead_id = ? ORDER BY id DESC LIMIT ?",
        (lead_id, limit),
    )
    rows = cursor.fetchall()
    conn.close()
    
    history = []
    for r in reversed(rows):
        role = "user" if r["sender"] == "user" else "assistant"
        history.append({"role": role, "content": r["message"]})
    return history

@client.event(MessageEv)
def on_message(client: NewClient, message: MessageEv):
    chat_jid = str(message.Info.MessageSource.Chat).lower()
    sender_jid = str(message.Info.MessageSource.Sender).lower()
    if message.Info.MessageSource.IsFromMe:
        return

    if "status@broadcast" in chat_jid or "status@broadcast" in sender_jid or "broadcast" in chat_jid:
        print("⏭️ Status/Broadcast update ignored.")
        return

    if chat_jid.endswith("@g.us") or sender_jid.endswith("@g.us"):
        print("⏭️ Group message ignored.")
        return
    
    msg_data = message.Message
    text = (
        msg_data.conversation
        or msg_data.extendedTextMessage.text
        or msg_data.imageMessage.caption
        or msg_data.videoMessage.caption
    )

    if not text:
        return

    sender_jid = message.Info.MessageSource.Chat
    try:
        sender_user = message.Info.MessageSource.Chat.User
    except AttributeError:
        sender_user = message.Info.SourceString.split("@")[0] if message.Info.SourceString else "Unknown"
    clean_phone = format_pk_phone(sender_jid.User)
    print(f"📩 Received text from {clean_phone}: {text}")

    user_activity = {
        "id": f"in-{message.Info.ID}",
        "type": "user",
        "text": "Received message from",
        "highlightText": clean_phone,
        "targetText": f'"{text}"',
        "time": "JUST NOW"
    }
    asyncio.run_coroutine_threadsafe(
        state_manager.add_activity(user_activity),
        loop
    )

    try:
        lead_id = get_create_lead(clean_phone)
        if not is_bot_enabled_for_lead(lead_id):
            print(f"⏸️ Bot is paused for lead #{lead_id} ({clean_phone}). Skipping AI response.")
            return

        # Save incoming user message to chat history
        save_chat_message(lead_id, "user", text)

        current_state = get_lead_state(lead_id)
        is_returning_lead = bool(
            current_state.get("intent")
            and current_state.get("intent") != "AWAITING INFO"
            and current_state.get("property_type")
        )

        system_prompt = f"""
You are an ultra-smart, polite, empathetic, and professional AI Real Estate Consultant for Malik Property (Mianwali). 
Your objective is to act like a natural human assistant (similar to Gemini/ChatGPT) and help clients gracefully.

DATABASE SAVED CLIENT PROFILE:
{json.dumps(current_state, indent=2)}

IS RETURNING LEAD: {is_returning_lead}

==================================================
LANGUAGE & SCRIPT MATCHING RULE (STRICT):
- Always match the EXACT language and script used by the user in their latest message:
  1. If the user writes in Arabic/Urdu Script (e.g. "السلام علیکم، مجھے مکان چاہیے"), respond strictly in URDU SCRIPT (اردو رسم الخط).
  2. If the user writes in Roman Urdu (e.g. "Assalam o alaikum, mujhe ghar chahiye"), respond strictly in ROMAN URDU.
  3. If the user writes in English, respond strictly in ENGLISH.

==================================================
CONVERSATIONAL & INTELLIGENCE RULES:
1. GEMINI-LIKE HUMAN BEHAVIOR:
   - Speak naturally like a real consultant, NOT a robotic survey bot.
   - Do NOT ask multiple questions in a single response. Ask a maximum of ONE follow-up question if required.
   - NEVER re-ask for details that are already present in the DATABASE SAVED CLIENT PROFILE.
   - Convince the client and guide him to work with you

2. RETURNING LEAD FLOW:
   - If IS RETURNING LEAD is True, acknowledge them warmly in their language/script.
   - Ask how you can assist them today.

3. CHAT CLOSING LOGIC:
   - If the client says closing/thanking words (e.g., "shukriya", "thank you", "ok", "allah hafiz", "شکریہ", "اللہ حافظ"), DO NOT ask any questions!
   - End the chat politely and gracefully in the user's script/language.

4. COMPLETE PROFILE HANDLING:
   - If intent, property_type, budget, and location are all collected, confirm that our team will reach out with short-listed properties shortly and conclude questioning.

5. BANNED WORDS:
   ❌ Banned Words (Hindi): swagat, namaste, kripya, dhanyawad, pranam.
   ✅ Allowed Equivalents: Khushamdeed / خوش آمدید, Assalam-o-Alaikum / السلام علیکم, Shukriya / شکریہ.

==================================================
Return ONLY a raw JSON object (no markdown, no ```json tags):
{{
    "reply": "Your natural response matching the user's exact language and script.",
    "name": "extracted name or null",
    "intent": "BUYING | SELLING | RENT | AWAITING INFO",
    "property_type": "string or null",
    "budget_min": float or null,
    "budget_max": float or null,
    "area": "string or null",
    "location": "string or null",
    "status": "NEW | FOLLOW UP | CLOSED | null"
}}
"""

        # Build multi-turn chat memory array for Groq API
        messages = [{"role": "system", "content": system_prompt}]
        chat_history = get_chat_history(lead_id, limit=8)
        messages.extend(chat_history)

        try:
            chat_completion = groq_client.chat.completions.create(
                messages=messages,
                model="openai/gpt-oss-120b",
                temperature=0.3,
                response_format={"type": "json_object"},
            )

            output_text = chat_completion.choices[0].message.content
            cleaned_text = output_text.replace("```json", "").replace("```", "").strip()
            data = json.loads(cleaned_text)

        except Exception as llm_error:
            print(f"⚠️ Groq / JSON Parse Error: {llm_error}")
            data = {
                "reply": "Assalam-o-Alaikum! Malik Property Mianwali mein khushamdeed. Main aapki kya madad kar sakta hoon?",
                "name": None,
                "intent": "AWAITING INFO",
                "property_type": None,
                "budget_min": None,
                "budget_max": None,
                "area": None,
                "location": None,
                "status": "NEW",
            }

        clean_intent = sanitize_intent(data.get("intent", "AWAITING INFO"))

        update_lead(
            lead_id=lead_id,
            name=data.get("name"),
            intent=clean_intent,
            property_type=data.get("property_type"),
            budget_min=data.get("budget_min"),
            budget_max=data.get("budget_max"),
            area=data.get("area"),
            location=data.get("location"),
            status=data.get("status"),
        )

        reply_text = data.get("reply", "Shukriya! Malik Property se rabta karne ka.")
        
        # Save bot outgoing reply to chat history
        save_chat_message(lead_id, "assistant", reply_text)

        client.send_message(to=sender_jid, message=reply_text)
        print(f"✅ Replied to {clean_phone}")

        bot_activity = {
            "id": f"out-{message.Info.ID}",
            "type": "bot",
            "text": "Bot replied to",
            "highlightText": clean_phone,
            "targetText": f'"{reply_text}"',
            "time": "JUST NOW"
        }

        asyncio.run_coroutine_threadsafe(
            state_manager.add_activity(bot_activity),
            loop
        )

    except Exception as e:
        print(f"❌ Error during message processing: {e}")

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
    client.connect()