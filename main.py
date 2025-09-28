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

# 📩 قالب الرسالة الأساسي
message_template = """👤 العميل: {full_name}
👨‍💼 شفت {Agent} سعـر البيـع {PriceIN}  
💰 المبلـغ: {much2} جنيه  
🏦 طريقة الدفع: {PaidBy} 
🛡️ رقم/اسم المحفظـة: {InstaControl}  
🧾 الإيصـال: {ShortUrl}  
💳 الرصيــد: {much} $ {Platform}
 {redid}
 {Note}"""

# 🔹 مفاتيح القالب الأساسية
template_keys = {
    "full_name", "username", "Agent", "PriceIN", "much2", "PaidBy",
    "InstaControl", "ShortUrl", "much", "Platform", "redid", "Note"
}

# 🔗 تحويل النص لرابط إذا كان URL (مع الإبقاء على النص الأصلي)
def make_clickable(value):
    if isinstance(value, str) and (value.startswith("http://") or value.startswith("https://")):
        return f'<a href="{value}">{value}</a>'
    return value

# إرسال رسالة لتليجرام
def send_to_telegram(message, buttons=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": GROUP_ID,
        "text": message,
        "reply_markup": {"inline_keyboard": buttons} if buttons else None,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
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
    thread = threading.Thread(target=run)
    thread.daemon = True
    thread.start()

keep_alive()

# 🟢 استقبال بيانات SendPulse
@app.route("/sendpulse", methods=["POST"])
def sendpulse():
    try:
        data = request.json or {}
        logging.info(f"📩 Data received: {data}")

        # تجهيز البيانات مع روابط قابلة للضغط
        filled_data = {k: make_clickable(v) if v else "" for k, v in data.items()}

        # ملء القالب
        message = message_template.format(
            full_name=filled_data.get("full_name", "غير محدد"),
            username=filled_data.get("username", "غير محدد"),
            Agent=filled_data.get("Agent", "غير محدد"),
            PriceIN=filled_data.get("PriceIN", "غير محدد"),
            much2=filled_data.get("much2", "غير محدد"),
            PaidBy=filled_data.get("PaidBy", "غير محدد"),
            InstaControl=filled_data.get("InstaControl", "غير محدد"),
            ShortUrl=filled_data.get("ShortUrl", "غير محدد"),
            much=filled_data.get("much", "غير محدد"),
            Platform=filled_data.get("Platform", "غير محدد"),
            redid=filled_data.get("redid", "غير محدد"),
            Note=filled_data.get("Note", "")
        )

        # إضافة أي متغيرات إضافية مش في القالب
        extra = ""
        for key, value in filled_data.items():
            if key not in template_keys:
                extra += f"\n🔹 <b>{key}</b>: {value}"
        if extra:
            message += "\n\n📌 <b>متغيرات إضافية</b>:" + extra

        # الأزرار (ثابتة حالياً)
        # الأزرار (صفين × 3)
        keyboard = [
            [
                {"text": "🔄 زر 1", "callback_data": "btn1"},
                {"text": "✅ زر 2", "callback_data": "btn2"},
                {"text": "❌ زر 3", "callback_data": "btn3"}
            ],
            [
                {"text": "💳 زر 4", "callback_data": "btn4"},
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
