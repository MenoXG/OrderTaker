# --- Fix imghdr issue in Python 3.13 ---
import sys
import imghdr_pure as imghdr
sys.modules['imghdr'] = imghdr
# --------------------------------------

import os
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# جلب التوكن ومعرف الجروب من متغيرات البيئة
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# إنشاء البوت
bot = Bot(token=TOKEN)
app = Flask(__name__)
application = Application.builder().token(TOKEN).build()

# عند استقبال رسالة جديدة
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_message:
        text = update.effective_message.text or ""
        # إعادة إرسال نفس الرسالة للجروب
        await bot.send_message(chat_id=CHAT_ID, text=text)

# إضافة الهاندلر للرسائل النصية
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# راوت استقبال webhook من تليجرام
@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    application.update_queue.put_nowait(update)
    return "ok", 200

# راوت أساسي للفحص
@app.route("/", methods=["GET"])
def index():
    return "Bot is running!", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
