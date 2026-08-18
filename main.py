import logging
import threading
import json
import os
from neonize.client import NewClient
from neonize.events import MessageEv, ConnectedEv
from groq import Groq
from database import (
    get_create_lead,
    converse_log,
    update_lead_info,
    init_db,
    get_history,
    save_buyer,
    save_seller,
    get_properties,
    get_property_by_id,
    get_last_matched_property_id
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

        prompt = f"""
You are the AI Real Estate Assistant for Malik Property (Mianwali). Your primary goal is to guide clients politely and systematically extract all required information while keeping the tone warm and conversational in the client's language (Urdu / Roman Urdu / English).

AVAILABLE INVENTORY:
{inventory}

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
   - If key information is missing for BUY or SELL, ask for 1 or 2 missing details at a time in your "reply".
   - Be helpful: answer their question or present inventory options while naturally asking for the next missing piece of information.
==================================================

INSTRUCTIONS:
- Return ONLY a raw JSON object (no markdown formatting, no code blocks).
- Set "matched_property_id" to integer property ID if discussing/recommending a specific listing, otherwise null.

Return this exact JSON structure:
{{
  "reply": "Your friendly response asking for missing details or helping the client",
  "client_name": "extracted name or null",
  "intent": "BUY or SELL or BOTH or INQUERY or null",
  "lead_tag": "HOT or WARM or COLD or null",
  "matched_property_id": integer property ID or null,
  "buyer_data": {{
      "preferred_location": "location name or null",
      "property_type": "Plot/House/Commercial/etc or null",
      "budget_range": "budget or null"
  }},
  "seller_data": {{
      "ownership_type": "fard_e_wahid or khata_shareek or null",
      "land_are": "area size or null",
      "mouza_location": "mouza/village or null",
      "doc_type": "Registry/Inteqal/Stamp or null",
      "asking_price": "price or null"
  }}
}}
"""

        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="openai/gpt-oss-20b",
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        output_text = chat_completion.choices[0].message.content
        data = json.loads(output_text)

        # Sanitize intent and tag values
        clean_intent = sanitize_intent(data.get("intent"))
        clean_tag = sanitize_tag(data.get("lead_tag"))

        update_lead_info(lead_id, data.get("client_name"), clean_intent, clean_tag)

        # Save buyer data if present (for BUY or BOTH)
        if data.get("buyer_data"):
            buyer = data["buyer_data"]
            if any(buyer.values()):
                save_buyer(
                    lead_id,
                    buyer.get("preferred_location"),
                    buyer.get("property_type"),
                    buyer.get("budget_range"),
                )

        # Save seller data if present (for SELL or BOTH)
        if data.get("seller_data"):
            seller = data["seller_data"]
            if any(seller.values()):
                save_seller(
                    lead_id,
                    seller.get("ownership_type"),
                    seller.get("land_are"),
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

            if property_record and hasattr(property_record, "__getitem__"):
                image_path = (
                    property_record["image_url"]
                    if "image_url" in property_record.keys()
                    else None
                )

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


if __name__ == "__main__":
    client.connect()
    threading.Event().wait()