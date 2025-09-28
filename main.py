import os
import logging
from flask import Flask, request, jsonify
import requests
import threading
import time

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")  # لازم يبدأ بـ -100
APP_URL = os.getenv("APP_URL")

# إرسال رسالة لتليجرام
def send_to_telegram(message, buttons=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": GROUP_ID,
        "text": message,
        "reply_markup": {"inline_keyboard": buttons} if buttons else None,
        "parse_mode": "HTML"
    }
    try:
        res = requests.post(url, json=payload)
        logging.info(f"✅ Telegram response: {res.text}")
    except Exception as e:
        logging.error(f"❌ Telegram error: {e}")

# 🔄 Keep Alive
def keep_alive():
    if not APP_URL:
        return
    def run():
        while True:
            try:
                requests.get(APP_URL)
                logging.info("🔄 Keep-alive ping sent")
            except Exception as e:
                logging.error(f"Ping error: {e}")
            time.sleep(300)
    import threading
    thread = threading.Thread(target=run)
    thread.daemon = True
    thread.start()

keep_alive()

# 🟢 استقبال بيانات SendPulse
@app.route("/sendpulse", methods=["POST"])
def sendpulse():
    try:
        data = request.json
        logging.info(f"📩 Data received: {data}")

        # بناء رسالة منظمة من كل المتغيرات
        message = "📩 <b>طلب جديد من SendPulse</b>\n\n"
        for key, value in data.items():
            if not value:
                value = "غير محدد"
            message += f"🔹 <b>{key}</b>: {value}\n"

        # الأزرار (ثابتة حالياً)
        keyboard = [
            [
                {"text": "🔄 زر 1", "callback_data": "btn1"},
                {"text": "✅ زر 2", "callback_data": "btn2"}
            ],
            [
                {"text": "❌ زر 3", "callback_data": "btn3"},
                {"text": "💳 زر 4", "callback_data": "btn4"}
            ],
            [
                {"text": "📞 زر 5", "callback_data": "btn5"},
                {"text": "📷 زر 6", "callback_data": "btn6"}
            ]
        ]

        send_to_telegram(message, keyboard)
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logging.error(f"❌ Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/", methods=["GET"])
def home():
    return "✅ Bot is running on Railway!"
