import os
import logging
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, CallbackQueryHandler

# إعداد logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# متغيرات البيئة
BOT_TOKEN = os.environ.get('BOT_TOKEN')
TELEGRAM_GROUP_ID = os.environ.get('TELEGRAM_GROUP_ID')

def create_keyboard():
    """إنشاء أزرار بسيطة"""
    keyboard = [
        [
            InlineKeyboardButton("✅ تم التعامل", callback_data="done"),
            InlineKeyboardButton("⏱ مؤجل", callback_data="later")
        ],
        [
            InlineKeyboardButton("📞 اتصل", callback_data="call"),
            InlineKeyboardButton("🗑 حذف", callback_data="delete")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def handle_message(update: Update, context):
    """معالجة الرسائل في الجروب"""
    try:
        message = update.message
        
        # تجاهل الرسائل من البوت نفسه
        if message.from_user and message.from_user.id == context.bot.id:
            return
        
        # الحصول على محتوى الرسالة
        if message.text:
            content = message.text
        else:
            content = "📨 رسالة تحتوي على ميديا"
        
        # إعادة إرسال الرسالة مع الأزرار
        await context.bot.send_message(
            chat_id=TELEGRAM_GROUP_ID,
            text=f"🔔 {content}",
            reply_markup=create_keyboard()
        )
        
        logger.info("تم إعادة إرسال الرسالة مع الأزرار")
        
    except Exception as e:
        logger.error(f"خطأ: {e}")

async def handle_button(update: Update, context):
    """معالجة النقر على الأزرار"""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    user = query.from_user
    
    # تحديث الرسالة
    await query.edit_message_text(
        text=f"{query.message.text}\n\n✅ تم التعامل بواسطة: {user.first_name}",
        reply_markup=None
    )

def main():
    """الدالة الرئيسية"""
    # التحقق من المتغيرات
    if not BOT_TOKEN or not TELEGRAM_GROUP_ID:
        logger.error("يجب ضبط BOT_TOKEN و TELEGRAM_GROUP_ID")
        return
    
    # إنشاء التطبيق
    application = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة handlers
    application.add_handler(MessageHandler(
        filters.Chat(chat_id=int(TELEGRAM_GROUP_ID)) & filters.TEXT,
        handle_message
    ))
    application.add_handler(CallbackQueryHandler(handle_button))
    
    logger.info("البوت يعمل ومراقب الجروب...")
    
    # بدء الاستماع للتحديثات
    application.run_polling()

if __name__ == '__main__':
    main()
