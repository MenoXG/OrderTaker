import os
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, CallbackQueryHandler, ContextTypes

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))  # لازم يبقى رقم سالب لو جروب

# التعامل مع الرسائل الجاية من القناة
async def channel_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.channel_post:
        text = update.channel_post.text or ""
        caption = update.channel_post.caption or ""

        if text:
            await context.bot.send_message(chat_id=GROUP_ID, text=text)

        elif update.channel_post.photo:
            file_id = update.channel_post.photo[-1].file_id
            await context.bot.send_photo(chat_id=GROUP_ID, photo=file_id, caption=caption)

        elif update.channel_post.video:
            file_id = update.channel_post.video.file_id
            await context.bot.send_video(chat_id=GROUP_ID, video=file_id, caption=caption)

        print("📩 تم تكرار الرسالة من القناة للجروب")

        # محاولة حذف الرسالة الأصلية من القناة
        try:
            await context.bot.delete_message(
                chat_id=update.channel_post.chat_id,
                message_id=update.channel_post.message_id
            )
            print("🗑️ تم حذف الرسالة الأصلية من القناة")
        except Exception as e:
            print("⚠️ لم يتم الحذف:", e)

# التعامل مع ضغط الأزرار
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await context.bot.send_message(chat_id=GROUP_ID, text=f"تم الضغط على الزر: {query.data}")
    print("🖲️ زر مضغوط:", query.data)

def main():
    app = Application.builder().token(TOKEN).build()

    # الهاندلرز
    app.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, channel_post_handler))
    app.add_handler(CallbackQueryHandler(button_handler))

    # تشغيل كـ webhook
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.getenv("PORT", 8080)),
        url_path="webhook",
        webhook_url=f"{os.getenv('RAILWAY_URL')}/webhook"
    )

if __name__ == "__main__":
    main()
