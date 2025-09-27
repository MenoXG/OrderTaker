import os
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, ContextTypes, MessageHandler, CallbackQueryHandler, filters

# ============= إعدادات من متغيرات البيئة =============
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROUP_ID = int(os.getenv("TELEGRAM_GROUP_ID"))  # الـ group اللي فيه البوت
SENDPULSE_BOT_ID = int(os.getenv("SENDPULSE_BOT_ID"))  # ID بتاع بوت SendPulse

PORT = int(os.getenv("PORT", 8080))  # Railway بيبعت PORT أوتوماتيك

# ============= إعداد التطبيق =============
app = Flask(__name__)
application = Application.builder().token(TOKEN).build()


# ============= التعامل مع الرسائل =============
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لما يوصل أي رسالة في الجروب"""
    if update.message and update.message.from_user.id == SENDPULSE_BOT_ID:
        text = update.message.text

        # أزرار
        keyboard = [
            [InlineKeyboardButton("✅ تم التحويل", callback_data="confirm")],
            [InlineKeyboardButton("❌ إلغاء الطلب", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # إعادة إرسال الرسالة في نفس الجروب
        await context.bot.send_message(
            chat_id=GROUP_ID,
            text=text,
            reply_markup=reply_markup
        )


async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """التعامل مع ضغط الأزرار"""
    query = update.callback_query
    await query.answer()

    if query.data == "confirm":
        await query.edit_message_text("✅ تم تأكيد الطلب")
    elif query.data == "cancel":
        await query.edit_message_text("❌ تم إلغاء الطلب")


# إضافة الهاندلرز
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
application.add_handler(CallbackQueryHandler(handle_button))


# ============= Flask Webhook =============
@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "ok", 200


@app.route("/")
def home():
    return "Bot is running!", 200


if __name__ == "__main__":
    # تشغيل Flask + البوت
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="webhook",
        webhook_url=f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN')}/webhook"
    )
    app.run(host="0.0.0.0", port=PORT)
