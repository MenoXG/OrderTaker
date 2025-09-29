from flask import Flask, request, jsonify
import requests
import os
import logging
from base64 import b64encode

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# ====== متغيرات البيئة ======
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # جروب/قناة الاستقبال
SENDPULSE_ID = os.getenv("SENDPULSE_API_ID")
SENDPULSE_SECRET = os.getenv("SENDPULSE_API_SECRET")

# ====== دوال المساعدة ======
def get_sendpulse_token():
    """جلب access_token جديد من SendPulse"""
    auth = b64encode(f"{SENDPULSE_ID}:{SENDPULSE_SECRET}".encode()).decode()
    r = requests.post(
        "https://api.sendpulse.com/oauth/access_token",
        data={"grant_type": "client_credentials"},
        headers={"Authorization": f"Basic {auth}"}
    )
    r.raise_for_status()
    return r.json()["access_token"]

def send_to_sendpulse(contact_id, text):
    """إرسال رسالة للعميل عبر SendPulse"""
    token = get_sendpulse_token()
    url = f"https://api.sendpulse.com/chatbots/sendText"
    payload = {
        "contact_id": contact_id,
        "text": text
    }
    r = requests.post(url, json=payload, headers={"Authorization": f"Bearer {token}"})
    logging.info(f"📤 SendPulse response: {r.text}")
    return r.json()

def send_to_telegram(msg, contact_id):
    """إرسال رسالة مع أزرار إلى جروب التليجرام"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    keyboard = {
        "inline_keyboard": [[
            {"text": "✅ تم التنفيذ", "callback_data": f"done|{contact_id}"},
            {"text": "❌ حذف", "callback_data": f"delete|{contact_id}"},
            {"text": "📷 إرسال صورة", "callback_data": f"photo|{contact_id}"}
        ]]
    }
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "reply_markup": keyboard,
        "disable_web_page_preview": True
    }
    r = requests.post(url, json=payload)
    logging.info(f"✅ Telegram response: {r.text}")
    return r.json()

# ====== استقبال بيانات من SendPulse ======
@app.route("/sendpulse", methods=["POST"])
def from_sendpulse():
    data = request.json
    logging.info(f"📩 Data from SendPulse: {data}")

    # نجمع البيانات الأساسية
    contact_id = data.get("contact_id")
    customer = data.get("full_name", "")
    username = data.get("username", "")
    agent = data.get("Agent", "")
    price_in = data.get("PriceIN", "")
    much2 = data.get("much2", "")
    paid_by = data.get("PaidBy", "")
    instacontrol = data.get("InstaControl", "")
    shorturl = data.get("ShortUrl", "")
    much = data.get("much", "")
    platform = data.get("Platform", "")
    redid = data.get("redid", "")
    note = data.get("Note", "")

    msg = (
        f"👤 العميل: {customer} تيليجرام: {username}\n"
        f"👨‍💼 شوفت {agent} سعـر البيـع {price_in}\n"
        f"💰 المبلغ: {much2} جنيه\n"
        f"🏦 طريقة الدفع: {paid_by}\n"
        f"🛡️ رقم/اسم المحفظـة: {instacontrol}\n"
        f"📝 الإيصـال: {shorturl}\n"
        f"💳 الرصيـد: {much} $ {platform}\n {redid}\n {note}"
    )

    send_to_telegram(msg, contact_id)
    return jsonify(ok=True)

# ====== استقبال الضغط على الأزرار من تليجرام ======
@app.route(f"/telegram/{TELEGRAM_TOKEN}", methods=["POST"])
def telegram_webhook():
    data = request.get_json(force=True)
    logging.info(f"📩 Update from Telegram: {data}")

    if "callback_query" in data:
        query = data["callback_query"]
        callback_id = query["id"]
        callback_data = query.get("data", "")
        message = query["message"]
        chat_id = message["chat"]["id"]
        message_id = message["message_id"]

        # ✅ لازم نرد بسرعة عشان الزر يبان شغال
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery",
                      json={"callback_query_id": callback_id})

        if "|" in callback_data:
            action, contact_id = callback_data.split("|", 1)

            if action == "done":
                send_to_sendpulse(contact_id, "✅ تم تنفيذ طلبك بنجاح")
            elif action == "delete":
                send_to_sendpulse(contact_id, "❌ تم إلغاء طلبك")
            elif action == "photo":
                send_to_sendpulse(contact_id, "📷 من فضلك أرسل صورة التحويل")

            # تحديث الرسالة في الجروب
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageReplyMarkup",
                          json={"chat_id": chat_id, "message_id": message_id, "reply_markup": {"inline_keyboard": []}})

    return jsonify(ok=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
