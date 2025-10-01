import os
import requests
from flask import Flask, request

app = Flask(__name__)

# ذاكرة مؤقتة (chat_id → contact_id)
pending_photos = {}

# =============================
# 1. دالة للحصول على Access Token من SendPulse
# =============================
def get_sendpulse_token():
    url = "https://api.sendpulse.com/oauth/access_token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": os.getenv("SENDPULSE_API_ID"),
        "client_secret": os.getenv("SENDPULSE_API_SECRET")
    }
    response = requests.post(url, data=payload)
    data = response.json()
    return data.get("access_token")

# =============================
# 2. إرسال رسالة للعميل عبر SendPulse
# =============================
def send_to_client(contact_id, text):
    token = get_sendpulse_token()
    url = f"https://api.sendpulse.com/telegram/contacts/sendText"
    payload = {"contact_id": contact_id, "text": text}
    headers = {"Authorization": f"Bearer {token}"}
    requests.post(url, json=payload, headers=headers)

# =============================
# 3. إرسال رسالة إلى جروب تليجرام مع أزرار
# =============================
def send_to_telegram(message, contact_id):
    token = os.getenv("TELEGRAM_TOKEN")
    group_id = os.getenv("GROUP_ID")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ تم التنفيذ", "callback_data": f"done:{contact_id}"},
                {"text": "❌ إلغاء", "callback_data": f"cancel:{contact_id}"},
            ],
            [
                {"text": "📷 إرسال صورة", "callback_data": f"sendpic:{contact_id}"}
            ]
        ]
    }
    payload = {
        "chat_id": group_id,
        "text": message,
        "parse_mode": "HTML",
        "reply_markup": keyboard
    }
    requests.post(url, json=payload)

# =============================
# 4. استقبال Webhook من SendPulse
# =============================
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json

    full_name = data.get("full_name", "")
    username = data.get("username", "")
    agent = data.get("Agent", "")
    price_in = data.get("PriceIN", "")
    much2 = data.get("much2", "")
    paid_by = data.get("PaidBy", "")
    instacontrol = data.get("InstaControl", "")
    short_url = data.get("ShortUrl", "")
    much = data.get("much", "")
    platform = data.get("Platform", "")
    redid = data.get("redid", "")
    note = data.get("Note", "")
    contact_id = data.get("contact_id", "")

    message = f"""
📩 <b>طلب جديد من {agent}</b>

👤 الاسم: {full_name}
🔗 يوزر العميل: @{username}
🆔 رقم ID: {redid}
💳 المنصة: {platform}
💰 المبلغ: {much}
💵 مايعادلها: {price_in}
📦 الكمية: {much2}
💲 طريقة الدفع: {paid_by}
👤 محول من: {instacontrol}
📝 ملاحظات: {note}
🔗 رابط الدفع: {short_url}
📞 Contact ID: {contact_id}
"""
    send_to_telegram(message, contact_id)
    return {"status": "ok"}, 200

# =============================
# 5. استقبال ضغط الأزرار + الصور من التليجرام
# =============================
@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    token = os.getenv("TELEGRAM_TOKEN")
    data = request.json

    # التعامل مع الأزرار
    if "callback_query" in data:
        callback = data["callback_query"]
        chat_id = callback["message"]["chat"]["id"]
        message_id = callback["message"]["message_id"]
        action = callback["data"]

        if action.startswith("done:"):
            contact_id = action.split(":")[1]
            send_to_client(contact_id, "✅ نعم تم تنفيذ طلبك بنجاح.")
            text = "✅ تم تنفيذ الطلب."
        elif action.startswith("cancel:"):
            contact_id = action.split(":")[1]
            send_to_client(contact_id, "❌ تم إلغاء طلبك.")
            text = "❌ تم إلغاء الطلب."
        elif action.startswith("sendpic:"):
            contact_id = action.split(":")[1]
            pending_photos[chat_id] = contact_id
            text = "📷 من فضلك ارفع صورة في الجروب وسأقوم بإرسالها للعميل."
        else:
            text = "ℹ️ عملية غير معروفة."

        # تعديل نص الرسالة في الجروب
        edit_url = f"https://api.telegram.org/bot{token}/editMessageText"
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML"
        }
        requests.post(edit_url, data=payload)

    # التعامل مع الصور
    if "message" in data and "photo" in data["message"]:
        chat_id = data["message"]["chat"]["id"]
        msg_id = data["message"]["message_id"]

        if chat_id in pending_photos:
            contact_id = pending_photos.pop(chat_id)
            photo = data["message"]["photo"][-1]
            file_id = photo["file_id"]

            # نجيب لينك مباشر للصورة
            file_info = requests.get(
                f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}"
            ).json()
            file_path = file_info["result"]["file_path"]
            file_url = f"https://api.telegram.org/file/bot{token}/{file_path}"

            # نبعته للعميل
            send_to_client(contact_id, f"📷 رابط الصورة: {file_url}")

            # نحذف الصورة من الجروب بعد الإرسال
            delete_url = f"https://api.telegram.org/bot{token}/deleteMessage"
            requests.post(delete_url, json={"chat_id": chat_id, "message_id": msg_id})

    return {"status": "ok"}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
