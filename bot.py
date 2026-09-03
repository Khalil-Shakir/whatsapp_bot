import json
import os
import sqlite3
import urllib.request
from groq import Groq
from neonize.client import NewClient
from neonize.events import MessageEv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "leads.db")
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
client = NewClient("auth_info.db")

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
        INSERT INTO leads (phone_number, last_interaction)
        VALUES (?, CURRENT_TIMESTAMP)
        ON CONFLICT(phone_number) DO UPDATE SET last_interaction=CURRENT_TIMESTAMP
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
    valid_intents = ["BUYING", "SELLING", "HOT LEAD", "AWAITING INFO"]
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


def notify_fastapi_dashboard(phone: str, name: str, intent: str, text: str):
    """Triggers FastAPI internal endpoint to notify frontend over WebSocket."""
    try:
        url = "http://localhost:8000/api/internal/broadcast-lead"
        payload = json.dumps({
            "phone_number": phone,
            "name": name or phone,
            "intent": intent,
            "message_text": text
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=2)
    except Exception as e:
        print(f"⚠️ Failed to send WS ping to FastAPI: {e}")

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
    clean_phone = format_pk_phone(sender_jid.User)
    print(f"📩 Received text from {clean_phone}: {text}")

    try:
        lead_id = get_create_lead(clean_phone)
        current_state = get_lead_state(lead_id)

        prompt = f"""
You are the AI Real Estate Assistant for Malik Property (Mianwali). Your goal is to politely collect property search or selling details while keeping a warm, natural tone in Urdu, Roman Urdu, or English.

CURRENT EXTRACTED CLIENT STATE:
{json.dumps(current_state, indent=2)}

INCOMING MESSAGE: "{text}"

==================================================
DATA EXTRACTION GUIDELINES:
1. Intent Mapping (MUST be one of these exact values):
   - "BUYING": Looking to buy/rent property.
   - "SELLING": Looking to sell property.
   - "HOT LEAD": Client shows urgent intent or high purchase confidence.
   - "AWAITING INFO": General questions or missing information.

2. Fields to Extract:
   - name: Client's full or first name.
   - property_type: Commercial, Residential, Plot, House, Agriculture.
   - budget_min: Minimum budget numeric value (in PKR or raw number).
   - budget_max: Maximum budget numeric value (in PKR or raw number).
   - status: Set to "HOT", "CONTACTED", "QUALIFIED", or "NEW".

3. Conversational & Language Rules:
   - DO NOT re-ask details already saved in CURRENT EXTRACTED CLIENT STATE.
   - Strict Urdu Vocabulary Enforcement:
     ❌ Banned Words (Hindi): swagat, namaste, kripya, dhanyawad, pranam.
     ✅ Allowed Equivalents: Khushamdeed, Assalam-o-Alaikum, Meherbani, Shukriya.

==================================================
Return ONLY raw JSON object (no markdown, no ```json formatting):
{{
  "reply": "Your response to the user asking missing information or acknowledging details.",
  "name": "extracted name or null",
  "intent": "BUYING or SELLING or HOT LEAD or AWAITING INFO",
  "property_type": "Plot/House/Commercial/etc or null",
  "budget_min": float number or null,
  "budget_max": float number or null,
  "status": "NEW or QUALIFIED or HOT or null"
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

        # Broadcast update to FastAPI WS Dashboard
        notify_fastapi_dashboard(
            phone=clean_phone,
            name=data.get("name") or current_state.get("name") or clean_phone,
            intent=clean_intent,
            text=text
        )

    except Exception as e:
        print(f"❌ Error during message processing: {e}")


if __name__ == "__main__":
    client.connect()