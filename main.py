import os
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # مثال: https://your-app.up.railway.app/webhook

app = Flask(__name__)
application = Application.builder().token(TOKEN).build()

# التعامل مع الرسائل
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    chat_id = message.chat_id

    # اتأكد إن الرسالة جاية من SendPulse Notifications bot
    if message.from_user and message.from_user.is_bot and "SendPulse" in message.from_user.first_name:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=message.message_id)
        except Exception as e:
            print("Delete failed:", e)

        keyboard = [
            [InlineKeyboardButton("✅ تم التنفيذ", callback_data="done")],
            [InlineKeyboardButton("❌ إلغاء الطلب", callback_data="cancel")],
            [InlineKeyboardButton("📷 إرفاق صورة", callback_data="attach")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(
            chat_id=chat_id,
            text=message.text,
            reply_markup=reply_markup
        )

# التعامل مع الأزرار
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "done":
        await query.edit_message_text("✅ تم تنفيذ الطلب")
    elif query.data == "cancel":
        await query.edit_message_text("❌ تم إلغاء الطلب")
    elif query.data == "attach":
        await query.edit_message_text("📷 من فضلك أرسل صورة الإيصال هنا")

# ربط Handlers
application.add_handler(CallbackQueryHandler(button_handler))
application.add_handler(MessageHandler(filters.ALL, handle_message))

# Flask webhook
@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "ok", 200

@app.route("/")
def index():
    return "Bot is running!", 200

if __name__ == "__main__":
    import asyncio
    if WEBHOOK_URL:
        async def set_webhook():
            await application.bot.set_webhook(WEBHOOK_URL)
            print(f"Webhook set to {WEBHOOK_URL}")
        asyncio.run(set_webhook())

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
