import os
import requests
from flask import Flask, request

app = Flask(__name__)

# ========== المتغيرات ==========
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_GROUP_ID")
SENDPULSE_API_ID = os.getenv("SENDPULSE_API_ID")
SENDPULSE_API_SECRET = os.getenv("SENDPULSE_API_SECRET")

# ========== التخزين المؤقت ==========
waiting_for_image = {}   # user_id -> contact_id
active_requests = {}     # user_id -> contact_id

# ========== دوال SendPulse ==========
def get_sendpulse_token():
    url = "https://api.sendpulse.com/oauth/access_token"
    data = {
        "grant_type": "client_credentials",
        "client_id": SENDPULSE_API_ID,
        "client_secret": SENDPULSE_API_SECRET,
    }
    r = requests.post(url, data=data)
    r.raise_for_status()
    return r.json()["access_token"]

def send_text_to_client(contact_id, text):
    token = get_sendpulse_token()
    url = "https://api.sendpulse.com/telegram/contacts/sendText"
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "contact_id": contact_id,
        "text": text,
    }
    r = requests.post(url, headers=headers, json=data)
    r.raise_for_status()
    return r.json()

# ========== دوال تليجرام ==========
def get_file_url(file_id):
    file_info = requests.get(
        f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
    ).json()
    file_path = file_info["result"]["file_path"]
    return f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

def delete_message(chat_id, message_id):
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage",
        data={"chat_id": chat_id, "message_id": message_id},
    )

# ========== Webhook ==========
@app.route("/", methods=["POST"])
def webhook():
    update = request.get_json()

    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        user_id = msg["from"]["id"]

        # --- حالة استلام CONTACT_ID من SendPulse (تعديل حسب شكل الرسالة) ---
        if "text" in msg and "CONTACT_ID" in msg["text"]:
            contact_id = msg["text"].split("CONTACT_ID:")[-1].strip()
            active_requests[user_id] = contact_id
            return {"ok": True}

        # --- حالة انتظار صورة ---
        if user_id in waiting_for_image and "photo" in msg:
            file_id = msg["photo"][-1]["file_id"]
            file_url = get_file_url(file_id)

            contact_id = waiting_for_image[user_id]
            send_text_to_client(contact_id, f"📷 صورة مرفقة: {file_url}")

            # حذف الصورة من الجروب
            delete_message(chat_id, msg["message_id"])

            # امسح الحالة
            waiting_for_image.pop(user_id, None)

            return {"ok": True}

    elif "callback_query" in update:
        cq = update["callback_query"]
        data = cq["data"]
        user_id = cq["from"]["id"]

        # --- زر إرسال صورة ---
        if data == "send_image":
            if user_id in active_requests:
                waiting_for_image[user_id] = active_requests[user_id]
                requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    data={
                        "chat_id": CHAT_ID,
                        "text": "📩 من فضلك أرسل صورة الآن",
                    },
                )

        # --- زر تنفيذ الطلب ---
        elif data == "approve_request":
            if user_id in active_requests:
                contact_id = active_requests[user_id]
                send_text_to_client(contact_id, "✅ تم تنفيذ طلبك بنجاح")

                # امسح الطلب من التخزين
                active_requests.pop(user_id, None)

                # امسح رسالة البوت في الجروب
                msg_id = cq["message"]["message_id"]
                delete_message(CHAT_ID, msg_id)

        return {"ok": True}

    return {"ok": True}

# ========== تشغيل السيرفر ==========
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
