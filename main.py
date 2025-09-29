import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# متغيرات البيئة (حط القيم الخاصة بيك هنا)
SENDPULSE_API_ID = os.getenv("SENDPULSE_API_ID")
SENDPULSE_API_SECRET = os.getenv("SENDPULSE_API_SECRET")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# كاش بسيط للـ access_token
sendpulse_token = None

def get_sendpulse_token():
    global sendpulse_token
    url = "https://api.sendpulse.com/oauth/access_token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": SENDPULSE_API_ID,
        "client_secret": SENDPULSE_API_SECRET
    }
    r = requests.post(url, data=payload)
    r.raise_for_status()
    data = r.json()
    sendpulse_token = data["access_token"]
    return sendpulse_token

def send_to_client(contact_id, message):
    global sendpulse_token
    if not sendpulse_token:
        sendpulse_token = get_sendpulse_token()

    url = "https://api.sendpulse.com/telegram/contacts/send"
    headers = {"Authorization": f"Bearer {sendpulse_token}"}
    payload = {
        "contact_id": contact_id,
        "message": message
    }
    r = requests.post(url, json=payload, headers=headers)
    if r.status_code == 401:  # token expired
        sendpulse_token = get_sendpulse_token()
        headers = {"Authorization": f"Bearer {sendpulse_token}"}
        r = requests.post(url, json=payload, headers=headers)
    return r.json()

@app.route(f"/webhook/{TELEGRAM_BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    data = request.json
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        # لو فيه contact_id جاي من الرسالة
        contact_id = None
        if "contact_id" in data["message"]:
            contact_id = data["message"]["contact_id"]

        # ارسال رسالة ترحيب مع أزرار
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ تم تنفيذ الطلب", "callback_data": f"done:{contact_id}"},
                    {"text": "🗑️ حذف الطلب", "callback_data": f"delete:{chat_id}"},
                    {"text": "📷 إرسال صورة", "callback_data": f"photo:{contact_id}"}
                ],
                [
                    {"text": "📄 زر إضافي 1", "callback_data": "extra1"},
                    {"text": "📄 زر إضافي 2", "callback_data": "extra2"},
                    {"text": "📄 زر إضافي 3", "callback_data": "extra3"}
                ]
            ]
        }

        requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": f"تم استقبال الطلب: {text}",
            "reply_markup": keyboard
        })

    elif "callback_query" in data:
        cq = data["callback_query"]
        cq_data = cq["data"]
        chat_id = cq["message"]["chat"]["id"]
        message_id = cq["message"]["message_id"]

        if cq_data.startswith("done:"):
            contact_id = cq_data.split(":")[1]
            if contact_id:
                send_to_client(contact_id, {
                    "type": "text",
                    "text": "تم تنفيذ طلبك بنجاح ✅"
                })
            # حذف الطلب من الجروب
            requests.post(f"{TELEGRAM_API_URL}/deleteMessage", json={
                "chat_id": chat_id,
                "message_id": message_id
            })

        elif cq_data.startswith("delete:"):
            # حذف الرسالة فقط من الجروب
            requests.post(f"{TELEGRAM_API_URL}/deleteMessage", json={
                "chat_id": chat_id,
                "message_id": message_id
            })

        elif cq_data.startswith("photo:"):
            contact_id = cq_data.split(":")[1]
            if contact_id:
                send_to_client(contact_id, {
                    "type": "photo",
                    "photo": "https://www.cdn.com/photo.png",
                    "caption": "صورة من المسؤول 📷"
                })

    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(port=5000, debug=True)
