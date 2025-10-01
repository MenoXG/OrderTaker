import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ---- متغيرات من Railway (زي الصورة اللي بعتلي) ----
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SENDPULSE_ID = os.getenv("SENDPULSE_ID")
SENDPULSE_SECRET = os.getenv("SENDPULSE_SECRET")
SENDPULSE_BOOK_ID = os.getenv("SENDPULSE_BOOK_ID")
SENDPULSE_API_URL = "https://api.sendpulse.com"

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# ---- دالة للحصول على توكن SendPulse ----
def get_sendpulse_token():
    url = f"{SENDPULSE_API_URL}/oauth/access_token"
    data = {
        "grant_type": "client_credentials",
        "client_id": SENDPULSE_ID,
        "client_secret": SENDPULSE_SECRET,
    }
    r = requests.post(url, data=data)
    r.raise_for_status()
    return r.json()["access_token"]

# ---- استقبال Webhook ----
@app.route("/", methods=["POST"])
def webhook():
    update = request.get_json(force=True)

    # ----- لو رسالة عادية -----
    if "message" in update:
        chat_id = update["message"]["chat"]["id"]

        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "📤 أرسل صورة", "callback_data": "send_image"},
                    {"text": "❌ إلغاء", "callback_data": "cancel"},
                ]
            ]
        }

        requests.post(f"{TELEGRAM_API}/sendMessage", json={
            "chat_id": chat_id,
            "text": "✅ تم تنفيذ طلبك بنجاح.\nاختر إجراء:",
            "reply_markup": keyboard
        })

    # ----- لو ضغط زر (callback_query) -----
    if "callback_query" in update:
        callback = update["callback_query"]
        chat_id = callback["message"]["chat"]["id"]
        data = callback["data"]

        # لازم نرد عشان الزرار ما يفضلش يحمل
        requests.post(f"{TELEGRAM_API}/answerCallbackQuery", json={
            "callback_query_id": callback["id"]
        })

        if data == "send_image":
            # هنا هنستخدم sendMessage ونبعت رابط صورة (انت بتتحكم في اللينك)
            photo_url = "https://example.com/sample.jpg"

            requests.post(f"{TELEGRAM_API}/sendMessage", json={
                "chat_id": chat_id,
                "text": f"📸 صورة من النظام:\n{photo_url}"
            })

        elif data == "cancel":
            requests.post(f"{TELEGRAM_API}/sendMessage", json={
                "chat_id": chat_id,
                "text": "❌ تم إلغاء العملية."
            })

    return jsonify({"ok": True})

# ---- تشغيل السيرفر ----
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
