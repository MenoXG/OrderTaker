import os
import logging
import time
import threading
import requests
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

# 🔑 المتغيرات من Railway
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")  # لازم يبدأ بـ -100
APP_URL = os.getenv("APP_URL")
SENDPULSE_API_ID = os.getenv("SENDPULSE_API_ID")
SENDPULSE_API_SECRET = os.getenv("SENDPULSE_API_SECRET")

# 🛡️ كاش للتوكين
sendpulse_token = None
sendpulse_token_expiry = 0

# 📩 قالب الرسالة
message_template = """👤 العميل: {full_name} تليجرام: {username}
👨‍💼 شفت {Agent} سعـر البيـع {PriceIN}  
💰 المبلـغ: {much2} جنيه  
🏦 طريقة الدفع: {PaidBy} 
🛡️ رقم/اسم المحفظـة: {InstaControl}  
🧾 الإيصـال: {ShortUrl}  
💳 الرصيــد: {much} $ {Platform}
 {redid}
 {Note}"""

# 🎯 مفاتيح القالب الأساسية
template_keys = {
    "full_name", "username", "Agent", "PriceIN", "much2", "PaidBy",
    "InstaControl", "ShortUrl", "much", "Platform", "redid", "Note", "contact_id"
}


# 🟢 دالة الحصول على توكين SendPulse
def get_sendpulse_token():
    global sendpulse_token, sendpulse_token_expiry
    if sendpulse_token and time.time() < sendpulse_token_expiry:
        return sendpulse_token

    url = "https://api.sendpulse.com/oauth/access_token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": SENDPULSE_API_ID,
        "client_secret": SENDPULSE_API_SECRET,
    }
    res = requests.post(url, data=payload)
    data = res.json()
    logging.info(f"🔑 SendPulse token response: {data}")
    sendpulse_token = data.get("access_token")
    sendpulse_token_expiry = time.time() + data.get("expires_in", 3600) - 60
    return sendpulse_token


# 📨 إرسال رسالة للعميل
def send_to_client(contact_id, message, msg_type="text", extra=None):
    token = get_sendpulse_token()
    url = "https://api.sendpulse.com/chatbots/sendMessage"
    headers = {"Authorization": f"Bearer {token}"}

    body = {
        "contact_id": contact_id,
        "message": {"type": msg_type},
    }

    if msg_type == "text":
        body["message"]["text"] = message
    elif msg_type == "photo":
        body["message"]["photo"] = extra.get("photo")
        body["message"]["caption"] = message
    elif msg_type == "file":
        body["message"]["file"] = extra.get("file")
        body["message"]["caption"] = message

    res = requests.post(url, headers=headers, json=body)
    logging.info(f"📤 SendPulse response: {res.text}")
    return res.ok


# 🔗 إرسال رسالة لتليجرام
def send_to_telegram(message, buttons=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": GROUP_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": buttons}
    try:
        res = requests.post(url, json=payload)
        logging.info(f"✅ Telegram response: {res.text}")
    except Exception as e:
        logging.error(f"❌ Telegram error: {e}")


# 🔄 Keep Alive
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

    thread = threading.Thread(target=run)
    thread.daemon = True
    thread.start()


keep_alive()

# 🟢 استقبال بيانات SendPulse
@app.route("/sendpulse", methods=["POST"])
def sendpulse():
    try:
        data = request.json or {}
        logging.info(f"📩 Data from SendPulse: {data}")

        contact_id = data.get("contact_id", "")

        filled_data = {k: v if v else "" for k, v in data.items()}

        message = message_template.format(
            full_name=filled_data.get("full_name", "غير محدد"),
            username=filled_data.get("username", "غير محدد"),
            Agent=filled_data.get("Agent", "غير محدد"),
            PriceIN=filled_data.get("PriceIN", "غير محدد"),
            much2=filled_data.get("much2", "غير محدد"),
            PaidBy=filled_data.get("PaidBy", "غير محدد"),
            InstaControl=filled_data.get("InstaControl", "غير محدد"),
            ShortUrl=filled_data.get("ShortUrl", "غير محدد"),
            much=filled_data.get("much", "غير محدد"),
            Platform=filled_data.get("Platform", "غير محدد"),
            redid=filled_data.get("redid", "غير محدد"),
            Note=filled_data.get("Note", ""),
        )

        # إضافة متغيرات إضافية
        extra = ""
        for key, value in filled_data.items():
            if key not in template_keys:
                extra += f"\n🔹 <b>{key}</b>: {value}"
        if extra:
            message += "\n\n📌 <b>متغيرات إضافية</b>:" + extra

        # أزرار مع contact_id
        keyboard = [
            [
                {"text": "✅ تم التنفيذ", "callback_data": f"done|{contact_id}"},
                {"text": "❌ حذف", "callback_data": f"delete|{contact_id}"},
                {"text": "📷 إرسال صورة", "callback_data": f"photo|{contact_id}"},
            ]
        ]

        send_to_telegram(message, keyboard)
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logging.error(f"❌ Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# 🟢 استقبال ضغط الأزرار من تليجرام
@app.route(f"/telegram/{TELEGRAM_TOKEN}", methods=["POST"])
def telegram_webhook():
    try:
        update = request.json
        logging.info(f"🤖 Telegram update: {update}")

        if "callback_query" in update:
            callback = update["callback_query"]
            data = callback["data"]  # مثال: done|672d2bc8...
            action, contact_id = data.split("|", 1)
            message_id = callback["message"]["message_id"]
            chat_id = callback["message"]["chat"]["id"]

            if action == "done":
                send_to_client(contact_id, "✅ تم تنفيذ طلبك بنجاح")
                delete_message(chat_id, message_id)

            elif action == "delete":
                delete_message(chat_id, message_id)

            elif action == "photo":
                send_to_client(
                    contact_id,
                    "📷 صورة مرفقة",
                    msg_type="photo",
                    extra={"photo": "https://www.cdn.com/photo.png"},
                )

        return jsonify({"ok": True})

    except Exception as e:
        logging.error(f"❌ Telegram webhook error: {e}")
        return jsonify({"ok": False}), 500


# 🗑️ حذف رسالة من جروب تليجرام
def delete_message(chat_id, message_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteMessage"
    payload = {"chat_id": chat_id, "message_id": message_id}
    requests.post(url, data=payload)


@app.route("/", methods=["GET"])
def home():
    return "✅ Bot is running on Railway!"
