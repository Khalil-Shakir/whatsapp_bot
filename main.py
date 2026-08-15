import logging
import threading
import os
from neonize.client import NewClient
from neonize.events import MessageEv, ConnectedEv
from google import genai


chatClient = genai.Client()
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
    interaction = chatClient.interactions.create(
        model = "gemini-3-flash-preview", input = f"you are agent of malik property from now. you handle the leads on whatsapp. answer to this query to the clint directly in the same language: {text}"
    )
    reply_text = f"*Bot*: {interaction.output_text}"
    client.reply_message(reply_text, message)
    print(f"Replied to {sender_jid.User}")


if __name__ == "__main__":
    client.connect()
    threading.Event().wait()