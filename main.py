import logging
import threading
import json
import os
import time
from neonize.client import NewClient
from neonize.events import (MessageEv, ConnectedEv, LoggedOutEv, DisconnectedEv)
from groq import Groq
from database import (
    get_create_lead, 
    format_pk_phone,
    update_lead_phone,
    converse_log,
    update_lead_info,
    init_db,
    get_history,
    save_buyer,
    save_seller,
    get_properties,
    get_property_by_id,
    get_last_matched_property_id,
    get_lead_state_payload
)
from utils.whatsapp import generate_wa_link, format_pk_phone

init_db()
groq_client = Groq()
logging.basicConfig(level=logging.INFO)
client = NewClient("auth_info.db")


def sanitize_intent(raw_intent):
    """Sanitize raw intent string from LLM to match SQLite CHECK constraint."""
    if not raw_intent or not isinstance(raw_intent, str):
        return None
    clean = raw_intent.strip().upper()
    if clean in ["BUY", "BUYER", "BUYING", "PURCHASE"]:
        return "BUY"
    elif clean in ["SELL", "SELLER", "SELLING"]:
        return "SELL"
    elif clean in ["BOTH", "BUY_AND_SELL", "SELL_AND_BUY"]:
        return "BOTH"
    elif clean in ["INQUERY", "INQUIRY", "INFO", "QUESTION", "GENERAL"]:
        return "INQUERY"
    return None


def sanitize_tag(raw_tag):
    """Sanitize lead_tag string from LLM."""
    if not raw_tag or not isinstance(raw_tag, str):
        return None
    clean = raw_tag.strip().upper()
    if clean in ["HOT", "WARM", "COLD"]:
        return clean
    return None


@client.event(ConnectedEv)
def on_connected(client: NewClient, __: ConnectedEv):
    print("✅ Malik Property Bot Online & Ready!")


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
        history = get_history(lead_id)
        converse_log(lead_id, "CLIENT", text)

        inventory = get_properties()

        history = get_history(lead_id)
        is_first_message = len(history) == 0
        state_payload = get_lead_state_payload(lead_id)
        prompt = f"""
You are the AI Real Estate Assistant for Malik Property (Mianwali). Your primary goal is to guide clients politely and systematically extract all required information while keeping the tone warm and conversational in the client's language (Urdu / Roman Urdu / English).

AVAILABLE INVENTORY:
{inventory}

CURRENT EXTRACTED CLIENT STATE (PERMANENT MEMORY):
{json.dumps(state_payload, indent=2)}

CONVERSATION HISTORY:
{history}

CURRENT USER MESSAGE: "{text}"

==================================================
DATA COLLECTION GUIDELINES:
1. Determine User Intent:
   - "BUY": Looking to purchase/rent property.
   - "SELL": Looking to list/sell property.
   - "BOTH": User wants to both buy and sell.
   - "INQUERY": Asking general questions.

2. Buyer Profile Requirements (Extract if Intent is BUY or BOTH):
   - Client Name
   - Preferred Location / Mouza
   - Property Type (Plot, House, Commercial, Agriculture)
   - Land Area / Size (e.g., 5 Marla, 10 Marla, 1 Kanal)
   - Budget Range

3. Seller Profile Requirements (Extract if Intent is SELL or BOTH):
   - Client Name
   - Mouza / Location of property
   - Land Area / Size (e.g., 5 Marla, 1 Kanal)
   - Asking Price
   - Ownership Type (fard_e_wahid or khata_shareek)
   - Document Type (Registry, Inteqal, Stamp)

4. Conversational Rules:
   - Check CONVERSATION HISTORY to see what details have ALREADY been provided.
   - DO NOT re-ask for details already captured.
   - GREETING RULES (STRICT):
     * FIRST MESSAGE STATUS: {"YES - Send initial greeting" if is_first_message else "NO - Ongoing conversation"}
     * If FIRST MESSAGE IS TRUE: Start your response with "Assalam-o-Alaikum! Malik Property mein khushamdeed."
     * If FIRST MESSAGE IS FALSE: DO NOT say "Assalam-o-Alaikum".
     * If the user says "Salam" or "Assalam-o-Alaikum" in an ongoing chat, reply ONLY with "Walaikum Assalam".
   - Check CONVERSATION HISTORY to see what details have ALREADY been provided.
   - DO NOT re-ask for details already captured.
   - If key information is missing for BUY or SELL, ask for 1 or 2 missing details at a time in your "reply".
   - Be helpful: answer their question or present inventory options while naturally asking for the next missing piece of information.


   ==================================================
   ==================================================
    LANGUAGE & VOCABULARY RULES (CRITICAL):
    - Target Languages: Standard Urdu, Pakistani Roman Urdu, or English.
    - STRICTLY PROHIBITED (HINDI WORDS): Never use Hindi vocabulary.
    ❌ Banned Words: sawagat, swagat, namaste, kripya, dhanyawad, kripya, aabhari, pranam.
    - ✅ Correct Roman Urdu Equivalents: 
    * "Khushamdeed" (not swagat)
    * "Meherbani" or "Barae meherbani" (not kripya)
    * "Shukriya" or "Nawazish" (not dhanyawad)
    * "Barah e karam" (not karipya)
    * "Assalam-o-Alaikum" (not namaste/pranam)
    ==================================================
INSTRUCTIONS:
- Return ONLY a raw JSON object (no markdown formatting, no code blocks).
- Set "matched_property_id" to integer property ID if discussing/recommending a specific listing, otherwise null.

Return this exact JSON structure:
{{
  "reply": "Your friendly response asking for missing details or helping the client",
  "client_name": "extracted name or null",
  "phone_number": "extracted phone number like 03001234567 or null",
  "intent": "BUY or SELL or BOTH or INQUERY or null",
  "lead_tag": "HOT or WARM or COLD or null",
  "matched_property_id": integer property ID or null,
  "buyer_data": {{
      "preferred_location": "location name or null",
      "property_type": "Plot/House/Commercial/etc or null",
      "land_area": "size like 10 Marla or 1 Kanal or null",
      "budget_range": "budget or null"
  }},
  "seller_data": {{
      "ownership_type": "fard_e_wahid or khata_shareek or null",
      "land_area": "area size or null",
      "mouza_location": "mouza/village or null",
      "doc_type": "Registry/Inteqal/Stamp or null",
      "asking_price": "price or null"
  }}
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
            
            # Clean potential markdown formatting block quotes standard to some models
            cleaned_text = output_text.replace("```json", "").replace("```", "").strip()
            data = json.loads(cleaned_text)

        except Exception as llm_error:
            print(f"⚠️ Groq / JSON Parse Error: {llm_error}")
            # Fallback dictionary so the script continues smoothly without crashing
            data = {
                "reply": "Assalam-o-Alaikum! Malik Property Mianwali mein xushamdeed. Main aapki kya madad kar sakta hoon? Barae meherbani apna naam aur phone number share kar dein.",
                "client_name": None,
                "phone_number": None,
                "intent": "INQUERY",
                "lead_tag": "WARM",
                "matched_property_id": None,
                "buyer_data": {},
                "seller_data": {}
            }

        # Sanitize intent and tag values
        clean_intent = sanitize_intent(data.get("intent"))
        clean_tag = sanitize_tag(data.get("lead_tag"))

        extracted_phone = data.get("phone_number")

        if extracted_phone:
            clean_extracted = format_pk_phone(extracted_phone)
            if clean_extracted:
                # Update phone_number directly in database for this lead ID
                lead_id = update_lead_phone(lead_id, clean_extracted)
        update_lead_info(lead_id, data.get("client_name"), clean_intent, clean_tag)

        # Save buyer data if present (for BUY or BOTH)
        if data.get("buyer_data"):
            buyer = data["buyer_data"]
            if any(buyer.values()):
                save_buyer(
                    lead_id,
                    buyer.get("preferred_location"),
                    buyer.get("property_type"),
                    buyer.get("land_area"),
                    buyer.get("budget_range"),
                )

        # Save seller data if present (for SELL or BOTH)
        if data.get("seller_data"):
            seller = data["seller_data"]
            if any(seller.values()):
                save_seller(
                    lead_id,
                    seller.get("ownership_type"),
                    seller.get("land_area"),
                    seller.get("mouza_location"),
                    seller.get("doc_type"),
                    seller.get("asking_price"),
                )

        reply_text = data.get("reply", "Thank you for contacting Malik Property.")

        # Resolve matched property ID
        raw_matched_id = data.get("matched_property_id")
        matched_id = None

        if isinstance(raw_matched_id, int):
            matched_id = raw_matched_id
        elif isinstance(raw_matched_id, str) and raw_matched_id.isdigit():
            matched_id = int(raw_matched_id)

        # Fallback: Check if user is requesting a photo for a property discussed earlier
        user_wants_image = any(
            kw in text.lower()
            for kw in ["pic", "picture", "tasveer", "photo", "dekhao", "bhejo", "image"]
        )
        if not matched_id and user_wants_image:
            matched_id = get_last_matched_property_id(lead_id)

        image_sent = False
        if matched_id:
            property_record = get_property_by_id(matched_id)

            if property_record:
                image_path = property_record["image_url"] if "image_url" in property_record.keys() else None

                if image_path and os.path.exists(image_path):
                    print(
                        f"📸 Sending property image for ID {matched_id} to {clean_phone}"
                    )
                    client.send_image(
                        to=sender_jid, file=image_path, caption=reply_text
                    )
                    image_sent = True
                else:
                    if image_path:
                        print(f"⚠️ Image path '{image_path}' not found on disk.")

        # Fallback to plain text message if image couldn't be sent
        if not image_sent:
            client.send_message(to=sender_jid, message=reply_text)

        log_entry = f"[ID: {matched_id}] {reply_text}" if matched_id else reply_text
        converse_log(lead_id, "BOT", log_entry)
        print(f"✅ Replied to {clean_phone}")

    except Exception as e:
        print(f"❌ Error during message processing: {e}")

@client.event(LoggedOutEv)
def on_logged_out(client: NewClient, __: LoggedOutEv):
    print("⚠️ ALERT: WhatsApp account logged out from device!")
    # Clear the invalidated auth database so neonize can regenerate a fresh QR on next startup
    if os.path.exists("auth_info.db"):
        os.remove("auth_info.db")
        print("🧹 Cleaned up invalid session file (auth_info.db). Re-run script to pair QR code.")

@client.event(DisconnectedEv)
def on_disconnected(client: NewClient, __: DisconnectedEv):
    print("🔌 WhatsApp disconnected from server. Retrying connection...")

if __name__ == "__main__":
    while True:
        try:
            print("🔄 Initializing WhatsApp Client...")
            client.connect()
            threading.Event().wait()
        except KeyboardInterrupt:
            print("🛑 Bot shut down manually.")
            break
        except Exception as err:
            print(f"❌ Connection dropped unexpectedly: {err}")
            print("⏳ Attempting automatic reconnection in 5 seconds...")
            time.sleep(5)