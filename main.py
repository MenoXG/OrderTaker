import os
import requests
from flask import Flask, request, jsonify
from io import BytesIO

app = Flask(__name__)

# متغيرات من Railway
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SENDPULSE_API_ID = os.getenv("SENDPULSE_API_ID")
SENDPULSE_API_SECRET = os.getenv("SENDPULSE_API_SECRET")
SENDPULSE_BASE_URL = "https://api.sendpulse.com"

# ذاكرة مؤقتة لحفظ contact_id أثناء انتظار الصورة
pending_images = {}

# دالة لجلب access_token من SendPulse
def get_sendpulse_token():
    url = f"{SENDPULSE_BASE_URL}/oauth/access_token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": SENDPULSE_API_ID,
        "client_secret": SENDPULSE_API_SECRET
    }
    r = requests.post(url, data=payload)
    r.raise_for_status()
    return r.json()["access_token"]

# دالة لتحميل الصورة من Telegram في الذاكرة
def download_telegram_file(file_id):
    # الحصول على مسار الملف
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}"
    r = requests.get(url)
    r.raise_for_status()
    file_path = r.json()["result"]["file_path"]

    # تنزيل الملف كبايتات في الذاكرة
    file_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
    response = requests.get(file_url)
    response.raise_for_status()
    return BytesIO(response.content), os.path.basename(file_path)

# دالة لإرسال الصورة للعميل
def send_image_to_client(contact_id, file_bytes, filename, caption="تم تنفيذ طلبك بنجاح ✅"):
    token = get_sendpulse_token()
    url = f"{SENDPULSE_BASE_URL}/telegram/contacts/sendPhoto"
    headers = {"Authorization": f"Bearer {token}"}
    files = {
        "photo": (filename, file_bytes),
    }
    data = {
        "contact_id": contact_id,
        "caption": caption
    }
    r = requests.post(url, headers=headers, data=data, files=files)
    r.raise_for_status()
    return r.json()

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json

    # ضغط زر "إرسال صورة"
    if "callback_query" in data:
        callback = data["callback_query"]
        chat_id = callback["message"]["chat"]["id"]
        contact_id = callback["data"].replace("send_image:", "")

        # حفظ contact_id مؤقتاً
        pending_images[chat_id] = contact_id

        # رد على الأدمن
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": "📷 من فضلك أرسل صورة الآن"}
        )

    # استقبال صورة من الأدمن
    elif "message" in data and "photo" in data["message"]:
        msg = data["message"]
        chat_id = msg["chat"]["id"]

        if chat_id in pending_images:
            contact_id = pending_images.pop(chat_id)
            file_id = msg["photo"][-1]["file_id"]  # أعلى جودة

            # تحميل الصورة في الذاكرة
            file_bytes, filename = download_telegram_file(file_id)

            # إرسال الصورة للعميل
            send_image_to_client(contact_id, file_bytes, filename)

            # مسح البافر من الذاكرة
            file_bytes.close()

            # رد على الأدمن
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": "✅ تم إرسال الصورة للعميل وحذفها من الذاكرة"}
            )

    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
