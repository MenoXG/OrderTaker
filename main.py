import os
import logging
from flask import Flask, request, jsonify
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

# إعداد اللوج
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = Flask(__name__)

# متغيرات البيئة
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")  # ID الجروب
bot = Bot(token=TELEGRAM_TOKEN)


@app.route("/sendpulse", methods=["POST"])
def sendpulse():
    try:
        data = request.json
        log.info(f"📩 Data received from SendPulse: {data}")

        # البيانات المستلمة
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

        # الأزرار (قابلة للتخصيص لاحقاً)
        keyboard = [
            [
                InlineKeyboardButton("🔄 زر 1", callback_data="btn1"),
                InlineKeyboardButton("✅ زر 2", callback_data="btn2"),
            ],
            [
                InlineKeyboardButton("❌ زر 3", callback_data="btn3"),
                InlineKeyboardButton("💳 زر 4", callback_data="btn4"),
            ],
            [
                InlineKeyboardButton("📞 زر 5", callback_data="btn5"),
                InlineKeyboardButton("📷 زر 6", callback_data="btn6"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # إرسال الرسالة للجروب
        bot.send_message(chat_id=GROUP_ID, text=message, reply_markup=reply_markup)

        return jsonify({"status": "ok"})
    except Exception as e:
        log.error(f"❌ Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/", methods=["GET"])
def home():
    return "✅ Bot is running on Railway!"
