import os
import logging
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# --- متغيرات البيئة ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")  # جروب الاستقبال
SENDPULSE_API_ID = os.environ.get("SENDPULSE_API_ID")
SENDPULSE_API_SECRET = os.environ.get("SENDPULSE_API_SECRET")

# كاش مؤقت لتوكين SendPulse
sendpulse_token = {"access_token": None, "expires_in": 0}

# ==============================
# دوال مساعدة
# ==============================
def get_sendpulse_token():
    """تجديد التوكين الخاص بـ SendPulse"""
    global sendpulse_token
    if not sendpulse_token["access_token"]:
        url = "https://api.sendpulse.com/oauth/access_token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": SENDPULSE_API_ID,
            "client_secret": SENDPULSE_API_SECRET
        }
        r = requests.post(url, data=payload)
        r.raise_for_status()
        sendpulse_token = r.json()
        logging.info(f"🔑 New SendPulse token: {sendpulse_token}")
    return sendpulse_token["access_token"]

def send_to_client(contact_id, text):
    """إرسال رسالة نصية للعميل عبر SendPulse"""
    url = f"https://api.sendpulse.com/chatbot/v1/messages/send"
    headers = {"Authorization": f"Bearer {get_sendpulse_token()}"}
    payload = {
        "contact_id": contact_id,
        "message": {
            "type": "text",
            "text": text
        }
    }
    r = requests.post(url, headers=headers, json=payload)
    logging.info(f"📤 SendPulse response: {r.text}")
    return r.json()

def format_order(data):
    """تجهيز الرسالة للتليجرام"""
    return (
        f"👤 العميل: {data.get('full_name','')} تليجرام: {data.get('username','')}\n"
        f"👨‍💼 شفـت {data.get('Agent','')} سعـر البيـع {data.get('PriceIN','')}\n"
        f"💰 المبلغ: {data.get('much2','')} جنيـه\n"
        f"🏦 طريقة الدفع: {data.get('PaidBy','')}\n"
        f"🛡 رقم/اسم المحفظة: {data.get('InstaControl','')}\n"
        f"📝 الإيصـال: {data.get('ShortUrl','')}\n"
        f"💳 الرصيد: {data.get('much','')} $ {data.get('Platform','')}\n"
        f"{data.get('redid','')}\n"
        f"{data.get('Note','')}"
    )

def send_to_telegram(data):
    """إرسال الرسالة إلى جروب التليجرام مع الأزرار"""
    text = format_order(data)
    contact_id = data.get("contact_id")

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ تم التنفيذ", "callback_data": f"done|{contact_id}"},
                {"text": "❌ حذف", "callback_data": f"delete|{contact_id}"},
                {"text": "📷 إرسال صورة", "callback_data": f"photo|{contact_id}"}
            ]
        ]
    }

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "disable_web_page_preview": True,
        "reply_markup": keyboard
    }
    r = requests.post(url, json=payload)
    logging.info(f"✅ Telegram response: {r.text}")
    return r.json()

# ==============================
# API Endpoints
# ==============================
@app.route("/sendpulse", methods=["POST"])
def from_sendpulse():
    data = request.json
    logging.info(f"📩 Data from SendPulse: {data}")
    send_to_telegram(data)
    return jsonify({"status": "ok"}), 200

@app.route(f"/telegram/{TELEGRAM_BOT_TOKEN}", methods=["POST"])
def from_telegram():
    update = request.json
    logging.info(f"📩 Update from Telegram: {update}")

    if "callback_query" in update:
        callback = update["callback_query"]
        action, contact_id = callback["data"].split("|")

        if action == "done":
            send_to_client(contact_id, "✅ تم تنفيذ طلبك بنجاح.")
        elif action == "delete":
            send_to_client(contact_id, "❌ تم إلغاء طلبك.")
        elif action == "photo":
            send_to_client(contact_id, "📷 من فضلك أرسل صورة الإيصال.")

        # حذف رسالة الطلب من الجروب
        chat_id = callback["message"]["chat"]["id"]
        message_id = callback["message"]["message_id"]
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteMessage"
        requests.post(url, json={"chat_id": chat_id, "message_id": message_id})

    return jsonify({"status": "ok"}), 200

@app.route("/", methods=["GET"])
def home():
    return "Bot is running ✅"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
