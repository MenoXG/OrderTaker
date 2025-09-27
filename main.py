import os
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# -------------------
# متغيرات البيئة
# -------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    raise ValueError("❌ لازم تضيف BOT_TOKEN و CHAT_ID في متغيرات البيئة على Railway")

# -------------------
# إعداد التليجرام بوت
# -------------------
app_telegram = Application.builder().token(BOT_TOKEN).build()

# دي الوظيفة اللي هتكرر أي رسالة جاية من قناة/بوت SendPulse
async def echo_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        text = update.message.text or ""
        # إرسال نسخة من الرسالة للجروب
        await context.bot.send_message(chat_id=CHAT_ID, text=f"🔁 {text}")

# مسك أي رسالة عادية جاية
app_telegram.add_handler(MessageHandler(filters.ALL, echo_message))

# -------------------
# إعداد Flask
# -------------------
app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, app_telegram.bot)
    app_telegram.update_queue.put_nowait(update)
    return "OK", 200

@app.route("/")
def home():
    return "🚀 Bot is running on Railway!", 200

# -------------------
# نقطة التشغيل
# -------------------
if __name__ == "__main__":
    import asyncio

    port = int(os.environ.get("PORT", 8080))
    async def run():
        await app_telegram.initialize()
        await app_telegram.start()
        await app_telegram.updater.start_polling()

    loop = asyncio.get_event_loop()
    loop.create_task(run())
    app.run(host="0.0.0.0", port=port)
