import os
import requests
from flask import Flask, request

app = Flask(__name__)

# متغيرات البيئة
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SENDPULSE_ID = os.getenv("SENDPULSE_ID")
SENDPULSE_SECRET = os.getenv("SENDPULSE_SECRET")
GROUP_ID = int(os.getenv("GROUP_ID"))  # رقم الجروب اللي بيجيله الطلبات

waiting_for_photo = {}

# دالة لجلب توكن SendPulse
def get_sendpulse_token():
    url = "https://api.sendpulse.com/oauth/access_token"
    data = {
        "grant_type": "client_credentials",
        "client_id": SENDPULSE_ID,
        "client_secret": SENDPULSE_SECRET
    }
    r = requests.post(url, data=data).json()
    return r["access_token"]

# إرسال صورة أو نص للعميل عبر SendPulse
def send_to_customer(contact_id, text=None, photo=None, caption=None):
    token = get_sendpulse_token()
    url = f"https://api.sendpulse.com/messages/v2/facebook/contacts/{contact_id}"

    if photo:
        payload = {
            "type": "image",
            "image": {
                "url": photo
            }
        }
        if caption:
            payload["caption"] = caption
    else:
        payload = {
            "type": "text",
            "text": text
        }

    headers = {"Authorization": f"Bearer {token}"}
    requests.post(url, json=payload, headers=headers)

# Webhook
@app.route("/", methods=["POST"])
def webhook():
    data = request.json

    # 👇 استلام الضغط على زر "إرسال صورة"
    if "callback_query" in data:
        callback = data["callback_query"]
        if callback["data"].startswith("send_image:"):
            contact_id = callback["data"].split(":")[1]
            chat_id = callback["message"]["chat"]["id"]

            waiting_for_photo[GROUP_ID] = contact_id

            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": "📷 من فضلك أرسل صورة الآن"}
            )

    # 👇 استلام صورة من الجروب
    elif "message" in data and "photo" in data["message"]:
        contact_id = waiting_for_photo.get(GROUP_ID)
        if contact_id:
            file_id = data["message"]["photo"][-1]["file_id"]

            # استدعاء getFile للحصول على رابط مباشر
            file_info = requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getFile",
                params={"file_id": file_id}
            ).json()

            file_path = file_info["result"]["file_path"]
            file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"

            # إرسال الصورة للعميل
            send_to_customer(
                contact_id,
                photo=file_url,
                caption="✅ تم تنفيذ طلبك بنجاح"
            )

            # مسح الحالة
            waiting_for_photo.pop(GROUP_ID, None)

            # حذف صورة الجروب تلقائياً بعد الإرسال
            chat_id = data["message"]["chat"]["id"]
            message_id = data["message"]["message_id"]
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteMessage",
                json={"chat_id": chat_id, "message_id": message_id}
            )

    return "ok"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
