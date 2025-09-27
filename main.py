import os
from flask import Flask, request
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Dispatcher, MessageHandler, filters, CallbackContext, CallbackQueryHandler
from telegram.ext import Application

TOKEN = os.getenv("TELEGRAM_TOKEN")
SENDPULSE_BOT_ID = int(os.getenv("SENDPULSE_BOT_ID"))  # ID بتاع بوت SendPulse
GROUP_ID = int(os.getenv("GROUP_ID"))  # معرف الجروب

app = Flask(__name__)
bot = Bot(token=TOKEN)

# لازم Dispatcher علشان يدير التحديثات
application = Application.builder().token(TOKEN).build()

# لما تيجي رسالة في الجروب
async def handle_group_message(update: Update, context: CallbackContext):
    if not update.message:
        return

    # لو المرسل هو بوت SendPulse
    if update.message.from_user and update.message.from_user.id == SENDPULSE_BOT_ID:
        text = update.message.text

        # احذف الرسالة الأصلية
        try:
            await bot.delete_message(chat_id=update.message.chat_id, message_id=update.message.message_id)
        except Exception as e:
            print("خطأ أثناء حذف الرسالة:", e)

        # ابعت نسخة جديدة من بوتك مع أزرار
        keyboard = [
            [InlineKeyboardButton("✅ تم", callback_data="done")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await bot.send_message(chat_id=GROUP_ID, text=text, reply_markup=reply_markup)

# لما يضغطوا على الأزرار
async def handle_button(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    if query.data == "done":
        await query.edit_message_text("✅ تم تنفيذ الطلب")
    elif query.data == "cancel":
        await query.edit_message_text("❌ تم إلغاء الطلب")

# نضيف الهاندلرز
application.add_handler(MessageHandler(filters.ChatType.GROUPS, handle_group_message))
application.add_handler(CallbackQueryHandler(handle_button))

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    application.update_queue.put(update)
    return "ok"

@app.route("/")
def home():
    return "Bot is running!"

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=PORT)
