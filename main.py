import os
from flask import Flask, request
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# ======================
# متغيرات البيئة
# ======================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")   # جروب/قناة اللي يبان فيها الرسالة المكررة
PORT = int(os.getenv("PORT", 8080))

# ======================
# Telegram Application
# ======================
app_telegram = Application.builder().token(BOT_TOKEN).build()

# أمر /start للتجربة
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 البوت شغال تمام!")

# لو جت أي رسالة في الجروب أو من بوت SendPulse
async def repeat_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
        text = update.message.text

        # أزرار مخصصة
        keyboard = [
            [InlineKeyboardButton("✅ تم", callback_data="done"),
             InlineKeyboardButton("❌ إلغاء", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # إرسال نسخة جديدة من الرسالة
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=f"🔔 إشعار جديد:\n\n{text}",
            reply_markup=reply_markup
        )

# التعامل مع ضغط الأزرار
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "done":
        await query.edit_message_text("✅ تم تأكيد الطلب")
    elif query.data == "cancel":
        await query.edit_message_text("❌ تم إلغاء الطلب")

# ربط الهاندلرز
app_telegram.add_handler(CommandHandler("start", start))
app_telegram.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, repeat_message))
app_telegram.add_handler(CallbackQueryHandler(button_handler))

# ======================
# Flask App
# ======================
app = Flask(__name__)

@app.route("/")
def index():
    return "Bot is running ✅"

@app.route("/webhook", methods=["POST"])
async def webhook():
    update = Update.de_json(request.get_json(force=True), app_telegram.bot)
    await app_telegram.process_update(update)
    return "ok"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
