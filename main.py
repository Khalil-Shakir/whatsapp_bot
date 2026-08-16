import logging
import threading
import json
from neonize.client import NewClient
from neonize.events import MessageEv, ConnectedEv
from google import genai
from groq import Groq
from database import (get_create_lead, converse_log, update_lead_info, init_db, get_history, save_buyer, save_seller)

init_db()
chatClient = genai.Client()
groq_client = Groq()
logging.basicConfig(level=logging.INFO)
client = NewClient("auth_info.db")


@client.event(ConnectedEv)
def on_connected(client: NewClient, __: ConnectedEv):
    print("✅ Malik Property Bot Online & Ready!")

@client.event(MessageEv)
def on_message(client: NewClient, message: MessageEv):
    if message.Info.MessageSource.IsFromMe: return

    msg_data = message.Message
    text = (
        msg_data.conversation or msg_data.extendedTextMessage.text or msg_data.imageMessage.caption or msg_data.videoMessage.caption
        )

    if not text: return

    sender_jid = message.Info.MessageSource.Chat
    print(f"📩 Received text from {sender_jid.User}: {text}")
    try:
        lead_id = get_create_lead(sender_jid.User)
        history = get_history(lead_id)
        converse_log(lead_id, "CLIENT", text)
        # prompt = f"""
        #         You are the AI Assistant for Malik Property. Answer clients politely and professionally in the same language they use (Urdu/English/Roman Urdu).
        
        #         CONVERSATION HISTORY:
        #         {history}
        
        #         CURRENT USER MESSAGE: "{text}"
        
        #         INSTRUCTIONS:
        #         You MUST respond ONLY with a raw JSON object (no markdown, no backticks).
        #         Return this exact structure:
        #         {{
        #         "reply": "Your message back to the client",
        #         "client_name": "extracted name or null",
        #         "intent": "BUY or SELL or INQUIRY or null",
        #         "lead_tag": "HOT or WARM or COLD or null",
        #         "buyer_data": {{
        #             "preferred_location": "location name or null",
        #             "property_type": "Plot/House/etc or null",
        #             "budget_range": "budget or null"
        #         }},
        #         "seller_data": {{
        #             "ownership_type": "fard_e_wahid or khata_shareek or null",
        #             "land_are": "area size or null",
        #             "mouza_location": "mouza/village or null",
        #             "doc_type": "Registry/Inteqal/Stamp or null",
        #             "asking_price": "price or null"
        #         }}
        #         }}
        #         """
            
        # interaction = chatClient.interactions.create(
        #     model = "gemini-3-flash-preview", input = prompt
        # )

        

        # output = (interaction.output_text.strip().replace("```json", "").replace("```", ""))
        # data = json.loads(output)

        prompt = f"""<system_instructions>
You are an expert Real Estate Consultant and Lead Qualification Assistant for Malik Property.

PRIMARY GOALS:
1. Build rapport, trust, and enthusiasm to convince clients to do business with Malik Property.
2. Interrogative Data Gathering: Extract required lead information organically over the conversation. Never ask more than 1 or 2 targeted questions per response to keep the client engaged.

BEHAVIOR & SALES GUIDELINES:
- **Language Policy**: Match the user's language seamlessly (Urdu, Roman Urdu, or English).
- **Tone**: Warm, highly professional, encouraging, and authoritative in the property market. Highlight value (e.g., clear documentation, best market prices, verified listings).
- **Consultative Strategy**:
  - Acknowledge and validate the client's needs before asking for details.
  - If `intent` is "BUY" and buyer fields are missing, ask for preferred location, property type, or budget step-by-step.
  - If `intent` is "SELL" and seller fields are missing, ask for ownership type, land area, mouza, document type, or asking price naturally.
  - Do not ask for all missing fields at once. Guide them conversationally.

OUTPUT FORMAT:
Respond ONLY with a valid JSON payload matching the target schema. Do not include markdown codeblock wrappers (e.g., ```json), introductory text, or concluding notes outside the JSON object.
</system_instructions>

<conversation_history>
{history}
</conversation_history>

<current_user_message>
{text}
</current_user_message>

<json_schema>
{{
  "reply": "Persuasive, polite response building trust and asking for missing information.",
  "client_name": null,
  "intent": null,
  "lead_tag": null,
  "buyer_data": {{
    "preferred_location": null,
    "property_type": null,
    "budget_range": null
  }},
  "seller_data": {{
    "ownership_type": null,
    "land_are": null,
    "mouza_location": null,
    "doc_type": null,
    "asking_price": null
  }}
}}
</json_schema>

<field_rules>
- "intent" choices: "BUY", "SELL", "INQUIRY", or null
- "lead_tag" choices: "HOT" (ready to deal/has full details), "WARM" (interested but missing details), "COLD" (vague/unresponsive), or null
- "ownership_type" choices: "fard_e_wahid", "khata_shareek", or null
- "doc_type" choices: "Registry", "Inteqal", "Stamp", or null
- Preserve previously extracted details from <conversation_history> into the JSON payload.
- If a field is missing or unknown, set it strictly to null.
</field_rules>"""
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"},  # Enforces valid JSON response
        )

        output_text = chat_completion.choices[0].message.content
        data = json.loads(output_text)

        update_lead_info(lead_id, data.get("client_name"), data.get("intent"), data.get("lead_tag"))
        #save buyer
        if data.get("intent") == "BUY" and data.get("buyer_data"):
            buyer_data = data["buyer_data"]
            save_buyer(lead_id, buyer_data.get("preferred_location"), buyer_data.get("property_type"), buyer_data.get("budget_range"))
        #save seller
        if data.get("intent") == "SELL" and data.get("seller_data"):
            seller = data["seller_data"]
            save_seller(lead_id, seller.get("ownership_type"), seller.get("land_are"), seller.get("mouza_location"), seller.get("doc_type"), seller.get("asking_price"))
        
        reply_text = data.get("reply", "Thank you for contacting Malik Property.")
        client.reply_message(reply_text, message)
        converse_log(lead_id, "BOT", reply_text)
        print(f"Replied to {sender_jid.User}")

    except Exception as e:
        print(f"❌ Error during message processing: {e}")
if __name__ == "__main__":
    client.connect()
    threading.Event().wait()