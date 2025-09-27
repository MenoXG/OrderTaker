import os
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackQueryHandler

# اقرأ التوكن و ID الجروب من المتغيرات
TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROUP_ID = int(os.environ.get("TELEGRAM_GROUP_ID"))
bot = Bot(token=TOKEN)

app = Flask(__name__)

# dispatcher عشان نعالج التحديثات
dispatcher = Dispatcher(bot, None, workers=0)

# دالة start
def start(update, context):
    update.message.reply_text("البوت شغال ✅")

# دالة للرسائل العادية
def echo(update, context):
    text = update.message.text
    bot.send_message(chat_id=GROUP_ID, text=f"رسالة جديدة: {text}")

# إضافة الهاندلرز
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, echo))

# Webhook endpoint
@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok"

# اختبار سريع
@app.route("/")
def index():
    return "البوت شغال 🚀"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
