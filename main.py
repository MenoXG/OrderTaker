import os
import logging
import requests
from flask import Flask, request

# إعداد اللوج
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

# متغيرات البيئة
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")  # معرف الجروب أو القناة

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"


@app.route("/sendpulse", methods=["POST"])
def sendpulse():
    try:
        data = request.json
        logging.info(f"📩 Data received: {data}")

        # البيانات المستلمة من SendPulse
        name = data.get("name", "غير محدد")
        user_id = data.get("id", "غير محدد")
        amount = data.get("amount", "غير محدد")
        payment = data.get("payment", "غير محدد")

        # الرسالة
        message = (
            f"📩 طلب جديد من SendPulse:\n\n"
            f"👤 الاسم: {name}\n"
            f"🆔 ID: {user_id}\n"
            f"💵 المبلغ: {amount}\n"
            f"💳 طريقة الدفع: {payment}"
        )

        # الأزرار (6 أزرار قابلة للتخصيص)
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "🔄 زر 1", "callback_data": "btn1"},
                    {"text": "✅ زر 2", "callback_data": "btn2"},
                ],
                [
                    {"text": "❌ زر 3", "callback_data": "btn3"},
                    {"text": "💳 زر 4", "callback_data": "btn4"},
                ],
                [
                    {"text": "📞 زر 5", "callback_data": "btn5"},
                    {"text": "📷 زر 6", "callback_data": "btn6"},
                ],
            ]
        }

        # إرسال عبر API تليجرام
        response = requests.post(
            TELEGRAM_API,
            json={
                "chat_id": GROUP_ID,
                "text": message,
                "reply_markup": keyboard,
            },
        )

        logging.info(f"✅ Telegram response: {response.text}")
        return {"status": "ok"}

    except Exception as e:
        logging.error(f"❌ Error: {e}")
        return {"status": "error", "message": str(e)}, 500


@app.route("/", methods=["GET"])
def home():
    return "✅ Bot is running on Railway!"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
