import os
import logging
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, CallbackQueryHandler, ContextTypes
import asyncio
from threading import Thread

# إعداد logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# متغيرات البيئة
BOT_TOKEN = os.environ.get('BOT_TOKEN')
TELEGRAM_GROUP_ID = os.environ.get('TELEGRAM_GROUP_ID')

# تخزين البوت
bot = None
application = None

def create_simple_keyboard():
    """إنشاء أزرار بسيطة"""
    keyboard = [
        [
            InlineKeyboardButton("✅ تم التعامل", callback_data="handled"),
            InlineKeyboardButton("⏱ مؤجل", callback_data="postponed")
        ],
        [
            InlineKeyboardButton("📞 اتصل", callback_data="call"),
            InlineKeyboardButton("🗑 حذف", callback_data="delete")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل في الجروب"""
    try:
        message = update.message
        
        # تجاهل الرسائل من البوت نفسه
        if message.from_user and message.from_user.id == bot.id:
            return
        
        # الحصول على محتوى الرسالة
        if message.text:
            content = message.text
        elif message.caption:
            content = message.caption
        else:
            content = "📨 رسالة تحتوي على ميديا"
        
        # إعادة إرسال الرسالة مع الأزرار
        await bot.send_message(
            chat_id=TELEGRAM_GROUP_ID,
            text=f"🔔 {content}",
            reply_markup=create_simple_keyboard()
        )
        
        logger.info("تم إعادة إرسال الرسالة مع الأزرار")
        
    except Exception as e:
        logger.error(f"خطأ: {e}")

async def handle_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة النقر على الأزرار"""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    user = query.from_user
    
    # تحديث الرسالة
    original_text = query.message.text
    new_text = f"{original_text}\n\n✅ تم التعامل بواسطة: {user.first_name}"
    
    await query.edit_message_text(
        text=new_text,
        reply_markup=None
    )

async def setup_bot():
    """إعداد البوت"""
    global bot, application
    
    application = Application.builder().token(BOT_TOKEN).build()
    bot = application.bot
    
    # إضافة handlers
    application.add_handler(MessageHandler(
        filters.Chat(chat_id=int(TELEGRAM_GROUP_ID)) & filters.TEXT,
        handle_group_message
    ))
    application.add_handler(CallbackQueryHandler(handle_button_click))
    
    logger.info("البوت يعمل ومراقب الجروب")

def run_bot():
    """تشغيل البوت"""
    asyncio.run(setup_bot())
    application.run_polling()

if __name__ == '__main__':
    # التحقق من المتغيرات
    if not BOT_TOKEN or not TELEGRAM_GROUP_ID:
        logger.error("يجب ضبط BOT_TOKEN و TELEGRAM_GROUP_ID")
        exit(1)
    
    # تشغيل البوت
    bot_thread = Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # إبقاء البرنامج يعمل
    try:
        while True:
            pass
    except KeyboardInterrupt:
        logger.info("إيقاف البوت")
