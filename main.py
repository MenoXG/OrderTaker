import os
import logging
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# ============= Telegram & SendPulse Config =============
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_GROUP_ID = os.getenv("TELEGRAM_GROUP_ID")
SENDPULSE_API_ID = os.getenv("SENDPULSE_API_ID")
SENDPULSE_API_SECRET = os.getenv("SENDPULSE_API_SECRET")

# تخزين الـ access_token في الذاكرة
SENDPULSE_ACCESS_TOKEN = None

# ========================================================

def get_sendpulse_token():
    """الحصول على Access Token من SendPulse"""
    global SENDPULSE_ACCESS_TOKEN
    url = "https://api.sendpulse.com/oauth/access_token"
    data = {
        "grant_type": "client_credentials",
        "client_id": SENDPULSE_API_ID,
        "client_secret": SENDPULSE_API_SECRET
    }
    r = requests.post(url, data=data)
    r.raise_for_status()
    token = r.json()["access_token"]
    SENDPULSE_ACCESS_TOKEN = token
    return token


def send_to_sendpulse(contact_id, photo_url=None, caption=""):
    """إرسال رسالة (نص أو صورة) لعميل عبر SendPulse"""
    global SENDPULSE_ACCESS_TOKEN
    if not SENDPULSE_ACCESS_TOKEN:
        get_sendpulse_token()

    url = "https://api.sendpulse.com/telegram/contacts/send"
    headers = {"Authorization": f"Bearer {SENDPULSE_ACCESS_TOKEN}"}

    if photo_url:
        payload = {
            "contact_id": contact_id,
            "message": {
                "type": "photo",
                "photo": photo_url,
                "caption": caption
            }
        }
    else:
        payload = {
            "contact_id": contact_id,
            "message": {
                "type": "text",
                "text": caption
            }
        }

    r = requests.post(url, json=payload, headers=headers)
    if r.status_code == 401:  # Token expired → جدد
        get_sendpulse_token()
        headers["Authorization"] = f"Bearer {SENDPULSE_ACCESS_TOKEN}"
        r = requests.post(url, json=payload, headers=headers)
    logging.info(f"📤 SendPulse response: {r.text}")
    return r.json()


def send_to_telegram(text, keyboard=None):
    """إرسال رسالة للجروب على Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_GROUP_ID,
        "text": text,
        "disable_web_page_preview": True,
    }
    if keyboard:
        payload["reply_markup"] = {"inline_keyboard": keyboard}
    r = requests.post(url, json=payload)
    logging.info(f"✅ Telegram response: {r.text}")
    return r.json()


def delete_message(chat_id, message_id):
    """حذف رسالة من التليجرام"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteMessage"
    payload = {"chat_id": chat_id, "message_id": message_id}
    r = requests.post(url, json=payload)
    logging.info(f"🗑️ Telegram delete response: {r.text}")
    return r.json()


@app.route("/", methods=["POST", "GET"])
def webhook():
    """الـ Webhook الأساسي"""
    if request.method == "POST":
        data = request.get_json()
        logging.info(f"📩 Incoming Data: {data}")

        # ------------------- Handling Callback -------------------
        if "callback_query" in data:
            callback = data["callback_query"]
            chat_id = callback["message"]["chat"]["id"]
            message_id = callback["message"]["message_id"]
            callback_data = callback["data"]
            action, contact_id = callback_data.split("|", 1)

            if action == "done":
                send_to_sendpulse(contact_id, caption="✅ تم تنفيذ طلبك بنجاح")
                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery",
                    json={"callback_query_id": callback["id"], "text": "تم التنفيذ ✅"}
                )

            elif action == "delete":
                delete_message(chat_id, message_id)
                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery",
                    json={"callback_query_id": callback["id"], "text": "تم الحذف ❌"}
                )

            elif action == "photo":
                send_to_sendpulse(contact_id, photo_url="https://www.cdn.com/photo.png", caption="📷 صورة التحويل")
                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery",
                    json={"callback_query_id": callback["id"], "text": "تم إرسال صورة 📷"}
                )

            return jsonify({"status": "callback processed"}), 200

        # ------------------- Handling Normal Order -------------------
        contact_id = data.get("contact_id")
        name = data.get("full_name", "")
        username = data.get("username", "")
        agent = data.get("Agent", "")
        price_in = data.get("PriceIN", "")
        amount = data.get("much2", "")
        paid_by = data.get("PaidBy", "")
        wallet = data.get("InstaControl", "")
        short_url = data.get("ShortUrl", "")
        balance = data.get("much", "")
        platform = data.get("Platform", "")
        redid = data.get("redid", "")
        note = data.get("Note", "")

        # رسالة للتليجرام
        message = (
            f"👤 العميل: {name} تليجرام: {username}\n"
            f"👨‍💼 شفت {agent} سعـر البيـع {price_in}  \n"
            f"💰 المبلـغ: {amount} جنيه  \n"
            f"🏦 طريقة الدفع: {paid_by} \n"
            f"🛡️ رقم/اسم المحفظـة: {wallet}  \n"
            f"🗾 الإيصـال: {short_url}  \n"
            f"💳 الرصيــد: {balance} $ {platform}\n {redid}\n {note}"
        )

        # لوحة الأزرار
        keyboard = [[
            {"text": "✅ تم التنفيذ", "callback_data": f"done|{contact_id}"},
            {"text": "❌ حذف", "callback_data": f"delete|{contact_id}"},
            {"text": "📷 إرسال صورة", "callback_data": f"photo|{contact_id}"}
        ]]

        send_to_telegram(message, keyboard)
        return jsonify({"status": "ok"}), 200

    return "Running", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
