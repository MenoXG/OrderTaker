import os
import requests
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

app = Flask(__name__)

# إعداد مجلد مؤقت لتخزين الصور
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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

# دالة لتحميل رابط مباشر للصورة من Telegram
def download_telegram_file(file_id):
    # الحصول على مسار الملف من Telegram
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}"
    r = requests.get(url)
    r.raise_for_status()
    file_path = r.json()["result"]["file_path"]

    # تنزيل الملف
    file_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
    local_filename = secure_filename(file_path.split("/")[-1])
    local_path = os.path.join(UPLOAD_FOLDER, local_filename)

    with requests.get(file_url, stream=True) as response:
        response.raise_for_status()
        with open(local_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

    return local_filename, local_path

# endpoint لتقديم الملفات المرفوعة (لازم Railway يسمح بكده)
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# دالة لإرسال صورة للعميل
def send_image_to_client(contact_id, photo_url, caption="تم تنفيذ طلبك بنجاح ✅"):
    token = get_sendpulse_token()
    url = f"{SENDPULSE_BASE_URL}/telegram/contacts/send"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {
        "contact_id": contact_id,
        "message": {
            "type": "photo",
            "photo": photo_url,
            "caption": caption
        }
    }
    r = requests.post(url, json=body, headers=headers)
    r.raise_for_status()
    return r.json()

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json

    # تحقق من وجود callback button
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

    # تحقق إذا كانت رسالة صورة
    elif "message" in data and "photo" in data["message"]:
        msg = data["message"]
        chat_id = msg["chat"]["id"]

        if chat_id in pending_images:
            contact_id = pending_images.pop(chat_id)
            file_id = msg["photo"][-1]["file_id"]  # أكبر جودة

            # تحميل الصورة مؤقتاً
            filename, local_path = download_telegram_file(file_id)
            public_url = f"https://{os.getenv('RAILWAY_STATIC_URL')}/uploads/{filename}"

            # إرسال الصورة للعميل
            send_image_to_client(contact_id, public_url)

            # مسح الصورة بعد الإرسال
            try:
                os.remove(local_path)
            except Exception as e:
                print("خطأ في حذف الصورة:", e)

            # رد على الأدمن
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": "✅ تم إرسال الصورة للعميل وحذفها من السيرفر"}
            )

    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
