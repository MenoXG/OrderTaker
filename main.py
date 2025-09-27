import os
import logging
import asyncio
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, CallbackQueryHandler

# إعداد logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# متغيرات البيئة
BOT_TOKEN = os.environ['BOT_TOKEN']
GROUP_ID = os.environ['TELEGRAM_GROUP_ID']

# إنشاء البوت
bot = Bot(token=BOT_TOKEN)

def make_keyboard():
    """صنع أزرار بسيطة"""
    buttons = [
        [InlineKeyboardButton("✅ تم", callback_data="done")],
        [InlineKeyboardButton("⏱ لاحقاً", callback_data="later")]
    ]
    return InlineKeyboardMarkup(buttons)

async def resend_message(update, context):
    """إعادة إرسال الرسالة"""
    try:
        msg = update.message
        
        # تجاهل رسائل البوت نفسه
        if msg.from_user.id == (await bot.get_me()).id:
            return
        
        # إعادة الإرسال مع الأزرار
        await bot.send_message(
            chat_id=GROUP_ID,
            text=f"🔔 {msg.text}",
            reply_markup=make_keyboard()
        )
        
    except Exception as e:
        logger.error(f"خطأ: {e}")

async def button_click(update, context):
    """معالجة الضغط على الأزرار"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text=f"{query.message.text}\n\n✅ تم التعامل",
        reply_markup=None
    )

async def main():
    """تشغيل البوت"""
    app = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة المعالجات
    app.add_handler(MessageHandler(filters.Chat(GROUP_ID) & filters.TEXT, resend_message))
    app.add_handler(CallbackQueryHandler(button_click))
    
    # البدء
    logger.info("بدأ البوت في المراقبة...")
    await app.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
