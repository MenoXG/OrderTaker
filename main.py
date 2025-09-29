import os
import logging
import requests
import time
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")  # يبدأ بـ -100
APP_URL = os.getenv("APP_URL")

SENDPULSE_API_ID = os.getenv("SENDPULSE_API_ID")
SENDPULSE_API_SECRET = os.getenv("SENDPULSE_API_SECRET")

# نخزن التوكن في الذاكرة
sendpulse_token = {"access_token": None, "expires_at": 0}

# ======================================================
# 🔑 Get SendPulse Access Token
def get_sendpulse_token():
    global sendpulse_token
    now = int(time.time())
    if sendpulse_token["access_token"] and sendpulse_token["expires_at"] > now:
        return sendpulse_token["access_token"]

    url = "https://api.sendpulse.com/oauth/access_token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": SENDPULSE_API_ID,
        "client_secret": SENDPULSE_API_SECRET
    }
    try:
        res = requests.post(url, data=payload).json()
        token = res.get("access_token")
        expires_in = res.get("expires_in", 3600)
        sendpulse_token["access_token"] = token
        sendpulse_token["expires_at"] = now + expires_in - 60  # ناقص دقيقة أمان
        logging.info("✅ Got new SendPulse token")
        return token
    except Exception as e:
        logging.error(f"❌ SendPulse token error: {e}")
        return None

# ======================================================
# 📩 Send message to Telegram
def send_to_telegram(message, buttons=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": GROUP_ID,
        "text": message,
        "parse_mode": "HTML",
    }
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": buttons}
    try:
        res = requests.post(url, json=payload)
        logging.info(f"✅ Telegram response: {res.text}")
        return res.json()
    except Exception as e:
        logging.error(f"❌ Telegram error: {e}")

# 🗑️ Delete Telegram message
def delete_telegram_message(message_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteMessage"
    payload = {"chat_id": GROUP_ID, "message_id": message_id}
    try:
        res = requests.post(url, data=payload)
        logging.info(f"🗑️ Deleted Telegram message {message_id}")
    except Exception as e:
        logging.error(f"❌ Delete error: {e}")

# ======================================================
# 💬 Send message to customer via SendPulse (Telegram)
def send_to_customer(contact_id, text=None, photo=None, caption=None):
    token = get_sendpulse_token()
    if not token:
        return

    headers = {"Authorization": f"Bearer {token}"}

    if photo:  # إرسال صورة
        url = "https://api.sendpulse.com/telegram/contacts/sendImage"
        payload = {
            "contact_id": contact_id,
            "image": photo,
            "caption": caption or ""
        }
    else:  # إرسال نص
        url = "https://api.sendpulse.com/telegram/contacts/sendText"
        payload = {
            "contact_id": contact_id,
            "text": text or ""
        }

    try:
        res = requests.post(url, json=payload, headers=headers).json()
        logging.info(f"📩 Sent to customer: {res}")
    except Exception as e:
        logging.error(f"❌ Send to customer error: {e}")

# ======================================================
# 🟢 استقبال بيانات SendPulse
@app.route("/sendpulse", methods=["POST"])
def sendpulse():
    try:
        data = request.json
        logging.info(f"📩 Data received: {data}")

        contact_id = data.get("contact_id", "غير محدد")

        # بناء رسالة من المتغيرات
        message = "📩 <b>طلب جديد من SendPulse</b>\n\n"
        for key, value in data.items():
            if not value:
                value = "غير محدد"
            message += f"🔹 <b>{key}</b>: {value}\n"

        # Inline keyboard (صفين × 3 أزرار)
        keyboard = [
            [
                {"text": "✅ تنفيذ الطلب", "callback_data": f"approve|{contact_id}"},
                {"text": "❌ حذف الطلب", "callback_data": f"delete|{contact_id}"},
                {"text": "🖼️ إرسال صورة", "callback_data": f"photo|{contact_id}"}
            ],
            [
                {"text": "📞 زر إضافي", "callback_data": f"extra1|{contact_id}"},
                {"text": "📦 زر إضافي", "callback_data": f"extra2|{contact_id}"},
                {"text": "ℹ️ زر إضافي", "callback_data": f"extra3|{contact_id}"}
            ]
        ]

        send_to_telegram(message, keyboard)
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logging.error(f"❌ Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ======================================================
# 🔘 Handle Telegram button clicks
@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def telegram_webhook():
    try:
        data = request.json
        logging.info(f"🔘 Telegram callback: {data}")

        if "callback_query" in data:
            cq = data["callback_query"]
            message_id = cq["message"]["message_id"]
            action, contact_id = cq["data"].split("|", 1)

            if action == "approve":
                send_to_customer(contact_id, text="✅ تم تنفيذ طلبك بنجاح")
                delete_telegram_message(message_id)

            elif action == "delete":
                delete_telegram_message(message_id)

            elif action == "photo":
                send_to_customer(
                    contact_id,
                    photo="https://www.cdn.com/photo.png",
                    caption="🖼️ هذه صورة تجريبية"
                )

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logging.error(f"❌ Callback error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ======================================================
@app.route("/", methods=["GET"])
def home():
    return "✅ Bot is running with SendPulse integration!"
