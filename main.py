import os
import logging
from flask import Flask, request, jsonify
import requests
import threading
import time

# إعداد اللوج
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

# متغيرات البيئة
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")  # لازم يبدأ بـ -100
APP_URL = os.getenv("APP_URL")    # رابط Railway الأساسي

# دالة لإرسال رسالة إلى تيليجرام
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

# 🔄 Keep Alive Ping
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
            time.sleep(300)  # كل 5 دقايق
    thread = threading.Thread(target=run)
    thread.daemon = True
    thread.start()

keep_alive()

# 🟢 استقبال POST من SendPulse
@app.route("/sendpulse", methods=["POST"])
def sendpulse():
    try:
        data = request.json
        logging.info(f"📩 Data received from SendPulse: {data}")

        # استخراج البيانات
        name = data.get("name", "غير محدد")
        user_id = data.get("id", "غير محدد")
        amount = data.get("amount", "غير محدد")
        payment = data.get("payment", "غير محدد")

        # الرسالة
        message = (
            f"📩 <b>طلب جديد من SendPulse</b>\n\n"
            f"👤 الاسم: {name}\n"
            f"🆔 ID: {user_id}\n"
            f"💵 المبلغ: {amount}\n"
            f"💳 طريقة الدفع: {payment}"
        )

        # الأزرار (6 أزرار قابلة للتعديل)
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

# 🟢 صفحة رئيسية للتأكد من التشغيل
@app.route("/", methods=["GET"])
def home():
    return "✅ Bot is running on Railway!"
