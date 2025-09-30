import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ==============================
#  متغيرات البيئة
# ==============================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")  # جروب الأدمنز
SENDPULSE_API_ID = os.getenv("SENDPULSE_API_ID")
SENDPULSE_API_SECRET = os.getenv("SENDPULSE_API_SECRET")

# ==============================
#  دوال مساعدة
# ==============================

def get_sendpulse_token():
    """الحصول على Access Token جديد من SendPulse (مدته ساعة)"""
    url = "https://api.sendpulse.com/oauth/access_token"
    data = {
        "grant_type": "client_credentials",
        "client_id": SENDPULSE_API_ID,
        "client_secret": SENDPULSE_API_SECRET
    }
    r = requests.post(url, data=data)
    r.raise_for_status()
    return r.json()["access_token"]


def send_text_to_client(contact_id, text):
    """إرسال رسالة نصية للعميل عبر SendPulse"""
    token = get_sendpulse_token()
    url = "https://api.sendpulse.com/telegram/contacts/sendText"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "contact_id": contact_id,
        "text": text
    }
    r = requests.post(url, headers=headers, json=payload)
    r.raise_for_status()
    return r.json()


def delete_message(chat_id, message_id):
    """مسح رسالة من التليجرام"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteMessage"
    payload = {"chat_id": chat_id, "message_id": message_id}
    return requests.post(url, data=payload).json()


def send_message(chat_id, text, reply_markup=None):
    """إرسال رسالة لتليجرام"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return requests.post(url, json=payload).json()


def get_file_url(file_id):
    """جلب رابط الصورة من تليجرام"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}"
    r = requests.get(url).json()
    if "result" in r:
        file_path = r["result"]["file_path"]
        return f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
    return None


# ==============================
#  Webhook للتليجرام
# ==============================

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json()

    # لو رسالة جاية من الجروب
    if "message" in update:
        message = update["message"]
        chat_id = message["chat"]["id"]
        message_id = message["message_id"]

        if str(chat_id) == str(GROUP_ID):
            # لو صورة
            if "photo" in message:
                file_id = message["photo"][-1]["file_id"]
                file_url = get_file_url(file_id)
                caption = message.get("caption", "")

                reply_markup = {
                    "inline_keyboard": [
                        [{"text": "📤 تنفيذ الطلب", "callback_data": f"execute_{message_id}"}]
                    ]
                }
                send_message(chat_id, f"📸 صورة مرفقة\n{caption}", reply_markup)

                # نخزن لينك الصورة في الرسالة نفسها علشان لما ننفذ نبعته للعميل
                message["file_url"] = file_url

            # لو نص
            elif "text" in message:
                text = message["text"]
                reply_markup = {
                    "inline_keyboard": [
                        [{"text": "📤 تنفيذ الطلب", "callback_data": f"execute_{message_id}"}]
                    ]
                }
                send_message(chat_id, f"📩 طلب جديد:\n\n{text}", reply_markup)

    # لو ضغط زر
    elif "callback_query" in update:
        cq = update["callback_query"]
        data = cq["data"]
        from_chat = cq["message"]["chat"]["id"]
        message_id = cq["message"]["message_id"]

        if data.startswith("execute_"):
            original_message_id = data.split("_")[1]

            # هنا نجيب بيانات العميل من النص (JSON)
            try:
                payload = cq["message"]["text"]
                if "contact_id" in payload:
                    contact_id = payload.split('"contact_id":"')[1].split('"')[0]
                else:
                    contact_id = None
            except Exception:
                contact_id = None

            if contact_id:
                # لو فيه صورة
                if "file_url" in cq["message"]:
                    file_url = cq["message"]["file_url"]
                    send_text_to_client(contact_id, f"✅ تم تنفيذ طلبك\nرابط الصورة: {file_url}")
                else:
                    send_text_to_client(contact_id, "✅ تم تنفيذ طلبك بنجاح")

                send_message(from_chat, "✅ تم إرسال رسالة للعميل")

            else:
                send_message(from_chat, "⚠️ لم يتم العثور على contact_id")

            # نحذف الرسائل
            delete_message(from_chat, original_message_id)
            delete_message(from_chat, message_id)

    return jsonify({"status": "ok"})


# ==============================
#  Health check
# ==============================
@app.route("/", methods=["GET"])
def index():
    return "Bot is running", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
