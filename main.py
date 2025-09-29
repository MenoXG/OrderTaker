import os
import logging
import requests
from flask import Flask, request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# من المتغيرات البيئية
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # جروب الاستقبال
SENDPULSE_URL = "https://api.sendpulse.com/method/sendMessage"  # مثال (غيّر لو مختلف)

# ==========================
# استقبال Webhook من SendPulse
# ==========================
@app.route("/sendpulse", methods=["POST"])
def from_sendpulse():
    data = request.json
    logging.info(f"📩 Data from SendPulse: {data}")

    full_name = data.get("full_name", "بدون اسم")
    much2 = data.get("much2", "")
    paid_by = data.get("PaidBy", "")
    short_url = data.get("ShortUrl", "")
    balance = f'{data.get("much", "")} $ {data.get("Platform", "")}'
    contact_id = data.get("contact_id", "")

    text = (
        f"👤 العميل: {full_name}\n"
        f"💰 المبلغ: {much2} جنيه\n"
        f"🏦 الدفع: {paid_by}\n"
        f"📝 الإيصال: {short_url}\n"
        f"💳 الرصيد: {balance}"
    )

    # أزرار مرتبطة بـ contact_id
    buttons = {
        "inline_keyboard": [[
            {"text": "✅ تم التنفيذ", "callback_data": f"done|{contact_id}"},
            {"text": "❌ حذف", "callback_data": f"delete|{contact_id}"},
            {"text": "📷 إرسال صورة", "callback_data": f"photo|{contact_id}"}
        ]]
    }

    res = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "reply_markup": buttons,
            "disable_web_page_preview": True
        }
    )
    logging.info(f"✅ Telegram response: {res.text}")
    return "ok"

# ==========================
# استقبال Webhook من Telegram
# ==========================
@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def from_telegram():
    data = request.json
    logging.info(f"🤖 Update from Telegram: {data}")

    if "callback_query" in data:
        callback = data["callback_query"]
        chat_id = callback["message"]["chat"]["id"]
        message_id = callback["message"]["message_id"]
        action, contact_id = callback["data"].split("|", 1)

        if action == "done":
            # رد على العميل من SendPulse
            requests.post(SENDPULSE_URL, json={
                "contact_id": contact_id,
                "message": "✅ تم تنفيذ طلبك بنجاح"
            })
            # تعديل رسالة الجروب
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageText", json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": "✅ تم التنفيذ"
            })

        elif action == "delete":
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteMessage", json={
                "chat_id": chat_id,
                "message_id": message_id
            })

        elif action == "photo":
            # هنا ممكن تضيف لوجيك رفع الصورة
            requests.post(SENDPULSE_URL, json={
                "contact_id": contact_id,
                "message": "📷 برجاء إرسال صورة التحويل"
            })

    return "ok"

# ==========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
