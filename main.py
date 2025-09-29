import os
import logging
from flask import Flask, request, jsonify
import requests
import threading
import time

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")  # لازم يبدأ بـ -100
APP_URL = os.getenv("APP_URL")

SENDPULSE_ID = os.getenv("SENDPULSE_ID")
SENDPULSE_SECRET = os.getenv("SENDPULSE_SECRET")

# ================== SendPulse Token ==================
access_token = None
token_expires = 0

def get_sendpulse_token():
    global access_token, token_expires
    if time.time() < token_expires - 60:
        return access_token
    url = "https://api.sendpulse.com/oauth/access_token"
    data = {
        "grant_type": "client_credentials",
        "client_id": SENDPULSE_ID,
        "client_secret": SENDPULSE_SECRET
    }
    res = requests.post(url, data=data)
    res.raise_for_status()
    resp = res.json()
    access_token = resp["access_token"]
    token_expires = time.time() + resp["expires_in"]
    logging.info("🔑 New SendPulse token fetched")
    return access_token

def send_to_client(contact_id, message, msg_type="text", extra=None):
    url = "https://api.sendpulse.com/chatbots/send"
    headers = {"Authorization": f"Bearer {get_sendpulse_token()}"}
    body = {"contact_id": contact_id, "message": {"type": msg_type}}

    if msg_type == "text":
        body["message"]["text"] = message
    elif msg_type == "photo":
        body["message"]["photo"] = message
        if extra:
            body["message"]["caption"] = extra

    res = requests.post(url, headers=headers, json=body)
    logging.info(f"📤 Sent to client {contact_id}: {res.text}")
    return res.ok

# ================== Telegram ==================
def send_to_telegram(message, buttons=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": GROUP_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": buttons}

    res = requests.post(url, json=payload)
    logging.info(f"✅ Telegram response: {res.text}")
    return res.json()

def delete_message(chat_id, msg_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteMessage"
    requests.post(url, json={"chat_id": chat_id, "message_id": msg_id})

# ================== Keep Alive ==================
def keep_alive():
    if not APP_URL:
        return
    def run():
        while True:
            try:
                requests.get(APP_URL)
                logging.info("🔄 Keep-alive ping sent")
            except Exception as e:
                logging.error(f"Ping error: {e}")
            time.sleep(300)
    threading.Thread(target=run, daemon=True).start()

keep_alive()

# ================== Webhook ==================
@app.route(f"/webhook/{TELEGRAM_TOKEN}", methods=["POST"])
def telegram_webhook():
    data = request.json
    logging.info(f"📩 Telegram update: {data}")

    # 📌 التعامل مع الضغط على زر
    if "callback_query" in data:
        cq = data["callback_query"]
        raw = cq.get("data", "")
        chat_id = cq["message"]["chat"]["id"]
        msg_id = cq["message"]["message_id"]

        logging.info(f"➡️ Callback data: {raw}")

        parts = raw.split("|")
        action = parts[0]
        contact_id = parts[1] if len(parts) > 1 else None

        if action == "done" and contact_id:
            send_to_client(contact_id, "✅ تم تنفيذ طلبك بنجاح")
            delete_message(chat_id, msg_id)

        elif action == "delete":
            delete_message(chat_id, msg_id)

        elif action == "photo" and contact_id:
            send_to_client(contact_id, "https://www.cdn.com/photo.png",
                           msg_type="photo", extra="📷 صورة من الدعم")

    return jsonify({"ok": True})

# ================== استقبال SendPulse ==================
@app.route("/sendpulse", methods=["POST"])
def sendpulse():
    data = request.json or {}
    logging.info(f"📩 Data from SendPulse: {data}")

    contact_id = data.get("contact_id", "0")

    message = f"""👤 العميل: {data.get('full_name','غير محدد')}  
💰 المبلغ: {data.get('much2','غير محدد')} جنيه  
🏦 الدفع: {data.get('PaidBy','غير محدد')}  
🧾 الإيصال: {data.get('ShortUrl','')}  
💳 الرصيد: {data.get('much','')} $ {data.get('Platform','')}
"""

    keyboard = [
        [
            {"text": "✅ تم التنفيذ", "callback_data": f"done|{contact_id}"},
            {"text": "❌ حذف", "callback_data": f"delete|{contact_id}"},
            {"text": "📷 إرسال صورة", "callback_data": f"photo|{contact_id}"}
        ]
    ]

    send_to_telegram(message, keyboard)
    return jsonify({"status": "ok"}), 200

@app.route("/", methods=["GET"])
def home():
    return "✅ Bot is running on Railway!"
