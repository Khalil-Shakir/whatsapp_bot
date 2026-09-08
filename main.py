import os
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
from neonize.events import ConnectedEv, DisconnectedEv, MessageEv
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

# client = NewClient("db/whatsapp.sqlite3")

client = NewClient("auth_info.db")

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

@app.patch("/api/leads/{lead_id}/status")
async def update_lead_status(lead_id: int, payload: UpdateStatusPayload):
    # Standardize incoming status string
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

    # Broadcast real-time update via WebSocket state manager
    await state_manager.add_activity({
        "type": "action",
        "text": f"Lead #{lead_id} status updated to",
        "highlightText": new_status,
        "time": "JUST NOW"
    })

    return {"status": "success", "lead_id": lead_id, "new_status": new_status}

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

@app.patch("api/inventory/{item_id}/status")
async def updateInventoryItemStatus(item_id: int, payload: UpdateInventoryStatusPayload):
    valid_statuses = ["AVAILABLE", "PENDING", "SOLD"]
    new_status = payload.status.upper()

    if not new_status in valid_statuses:
        raise HTTPException(status_code=400, detail="Invalid status value")

    connect = get_db_connection()
    cursor = connect.cursor()
    cursor.execute("UPDATE inventory SET status = ? WHERE id = ?",(new_status, item_id))

    if cursor.rowcount == 0:
        connect.close()
        raise HTTPException(status_code=404, detail="Inventory item not found")

    connect.close()

    await state_manager.add_activity({
        "type" : "action",
        "text" : f"Property listing #{item_id} status updated to ",
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
    # Ensure ID exists
        if "id" not in activity or not activity["id"]:
            activity["id"] = f"act-{time.time_ns()}"

        # Deduplicate against existing activities in memory
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

        # Send ONLY the new activity payload to avoid triggering fallback handlers
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

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

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
    logger.warning("WhatsApp bot disconnected!")
    asyncio.run_coroutine_threadsafe(
        state_manager.update_status("DISCONNECTED", None),
        loop
    )

@client.event(MessageEv)
def on_message(client_instance, message: MessageEv):
    sender = message.Info.Sender.User
    text_content = message.Message.conversation or message.Message.extendedTextMessage.text or "[Media/Other]"

    activity = {
        "id": str(message.Info.ID),
        "type": "bot",
        "text": "Message received from",
        "highlightText": sender,
        "targetText": f'"{text_content}"',
        "time": "JUST NOW"
    }

    asyncio.run_coroutine_threadsafe(
        state_manager.add_activity(activity),
        loop
    )

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
            phone TEXT,
            intent TEXT,
            property_type TEXT,
            budget TEXT,
            status TEXT DEFAULT 'NEW',
            added_time TEXT
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

@app.get("/api/inventory", response_model=Dict[str, Any])
async def get_inventory(page: int, limit: int = 6):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        offset = (page-1)*limit
        cursor.execute("SELECT COUNT(*) FROM inventory")
        total_items = cursor.fetchone()[0] or 0
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
            "limit":limit,
            "total_pages": ()
        }
    except Exception as e:
        logger.error(f"Error in GET /api/inventory: {e}")
        return {"items":[], "total_items": 0, "page":1, "limit":limit, "total_pages":1}

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
    image_url = "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=600&auto=format&fit=crop"

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
            (title, price, type, location, beds, baths, sqft, status, dateAdded, image_url),
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
        await state_manager.broadcast({"event": "INVENTORY_UPDATED", "item": item})
        return item
    except Exception as e:
        logger.error(f"Error saving to inventory: {e}")
        return {"error": "Failed to add inventory item"}

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

            # Handle phone vs phone_number
            phone = (
                r["phone_number"]
                if "phone_number" in keys
                else (r["phone"] if "phone" in keys else "N/A")
            )

            # Format budget from budget_min / budget_max or fallback to budget
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

            # Handle last_interaction / created_at / added_time
            added_time = (
                r["last_interaction"]
                if "last_interaction" in keys and r["last_interaction"]
                else (
                    r["created_at"]
                    if "created_at" in keys and r["created_at"]
                    else (
                        r["added_time"]
                        if "added_time" in keys and r["added_time"]
                        else "Recently"
                    )
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
                    "status": (r["status"] or "NEW").upper(),
                    "botEnabled": bool(r["bot_enabled"]) if "bot_enabled" in keys and r["bot_enabled"] is not None else True,
                    "addedTime": added_time,
                }
            )

        return leads
    except Exception as e:
        logger.error(f"Error fetching leads: {e}")
        return []

#Bot functionlity#
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "leads.db")
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def format_pk_phone(phone_user: str) -> str:
    digits = "".join(filter(str.isdigit, str(phone_user)))
    if digits.startswith("92") and len(digits) == 12:
        return "0" + digits[2:]
    return digits


def get_create_lead(phone: str) -> int:
    conn = sqlite3.connect("leads.db")
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
    conn = sqlite3.connect("leads.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT phone_number, name, intent, property_type, budget_min, budget_max, status 
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
    status: str = None,
):
    conn = sqlite3.connect("leads.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE leads 
        SET name = COALESCE(?, name),
            intent = COALESCE(?, intent),
            property_type = COALESCE(?, property_type),
            budget_min = COALESCE(?, budget_min),
            budget_max = COALESCE(?, budget_max),
            status = COALESCE(?, status),
            last_interaction = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (name, intent, property_type, budget_min, budget_max, status, lead_id),
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
    return True # Default to enabled if not explicitly set

@client.event(MessageEv)
def on_message(client: NewClient, message: MessageEv):
    if message.Info.MessageSource.IsFromMe:
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
        current_state = get_lead_state(lead_id)

        prompt = f"""
        You are the AI Real Estate Assistant for Malik Property (Mianwali). Your goal is to politely collect property search or selling details while keeping a warm, natural tone in Urdu, Roman Urdu, or English.

        CURRENT EXTRACTED CLIENT STATE:
        {json.dumps(current_state, indent=2)}

        INCOMING MESSAGE: "{text}"

        ==================================================
        DATA EXTRACTION GUIDELINES:
        1. Intent Mapping (MUST be one of these exact values):
        - "BUYING": Looking to buy property.
        - "SELLING": Looking to sell property.
        - "RENT": Looking to rent property.

        2. Fields to Extract:
        - name: Client's full or first name.
        - property_type: Commercial, Residential, Plot, House, Agriculture.
        - budget_min: Minimum budget numeric value (in PKR, handle "lakh" / "crore" conversions if applicable).
        - budget_max: Maximum budget numeric value (in PKR, handle "lakh" / "crore" conversions if applicable).
        - status: Set to "NEW", "FOLLOW UP", or "CLOSED".

        3. Conversational & Language Rules:
        - DO NOT re-ask details already saved in CURRENT EXTRACTED CLIENT STATE.
        - Strict Urdu Vocabulary Enforcement:
            ❌ Banned Words (Hindi): swagat, namaste, kripya, dhanyawad, pranam.
            ✅ Allowed Equivalents: Khushamdeed, Assalam-o-Alaikum, Meherbani, Shukriya.

        ==================================================
        Return ONLY a raw JSON object (no markdown, no ```json formatting):
        {{
        "reply": "Your response to the user asking for missing information or acknowledging details.",
        "name": "extracted name or null",
        "intent": "BUYING | SELLING | RENT | AWAITING INFO,
        "property_type": "Plot/House/Commercial/etc or null",
        "budget_min": float number or null,
        "budget_max": float number or null,
        "status": "NEW | FOLLOW UP | CLOSED | null"
        }}
        """

        try:
            chat_completion = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="openai/gpt-oss-20b",
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
            status=data.get("status"),
        )

        reply_text = data.get("reply", "Shukriya! Malik Property se rabta karne ka.")
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