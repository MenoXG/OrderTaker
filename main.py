import os
import logging
import asyncio
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, CallbackQueryHandler, ContextTypes

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
    """إنشاء أزرار تفاعلية"""
    keyboard = [
        [
            InlineKeyboardButton("✅ تم التعامل", callback_data="done"),
            InlineKeyboardButton("⏱ مؤجل", callback_data="later")
        ],
        [
            InlineKeyboardButton("📞 اتصل بالعميل", callback_data="call"),
            InlineKeyboardButton("🗑 حذف الطلب", callback_data="delete")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة جميع الرسائل في الجروب"""
    try:
        message = update.message
        
        # تجاهل الرسائل من البوت نفسه
        if message.from_user and message.from_user.id == context.bot.id:
            return
        
        # الحصول على النص
        message_text = message.text or message.caption or ""
        
        logger.info(f"📨 رسالة مستلمة: {message_text[:100]}...")
        
        # كلمات SendPulse المفتاحية
        sendpulse_keywords = [
            "SendPulse Notifications", "سعر البيع", "شفت", "جنيه",
            "goolnk.com", "الرصيد", "Vodafone", "Instapay", "للبحرام",
            "الحميل", "RedotPay", "Binance", "Bybit", "السبع", "تحويل من"
        ]
        
        # التحقق إذا كانت رسالة SendPulse
        is_sendpulse = any(keyword in message_text for keyword in sendpulse_keywords)
        
        if is_sendpulse:
            logger.info("✅ تم التعرف على رسالة SendPulse!")
            
            # إعادة إرسال الرسالة مع الأزرار
            formatted_message = f"🛒 **طلب SendPulse**\n\n{message_text}\n\n⚡ **تم التوجيه تلقائياً**"
            
            await context.bot.send_message(
                chat_id=TELEGRAM_GROUP_ID,
                text=formatted_message,
                reply_markup=create_keyboard(),
                parse_mode='Markdown'
            )
            
            logger.info("✅ تم إعادة إرسال الرسالة بنجاح")
        else:
            logger.info("🚫 ليست رسالة SendPulse - تم تجاهلها")
            
    except Exception as e:
        logger.error(f"❌ خطأ في معالجة الرسالة: {e}")

async def handle_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة النقر على الأزرار"""
    try:
        query = update.callback_query
        await query.answer()
        
        user = query.from_user
        action = query.data
        
        logger.info(f"🔘 زر مضغوط: {action} بواسطة {user.first_name}")
        
        # تحديث الرسالة
        new_text = f"{query.message.text}\n\n---\n✅ تم التعامل: {action}\n👤 بواسطة: {user.first_name}"
        
        await query.edit_message_text(
            text=new_text,
            reply_markup=None,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"❌ خطأ في معالجة الزر: {e}")

def main():
    """الدالة الرئيسية"""
    try:
        # التحقق من المتغيرات البيئية
        if not BOT_TOKEN:
            logger.error("❌ BOT_TOKEN غير مضبوط!")
            return
        if not TELEGRAM_GROUP_ID:
            logger.error("❌ TELEGRAM_GROUP_ID غير مضبوط!")
            return
        
        logger.info("🚀 بدء تشغيل بوت SendPulse...")
        
        # إنشاء التطبيق
        application = Application.builder().token(BOT_TOKEN).build()
        
        # إضافة handlers
        application.add_handler(MessageHandler(
            filters.Chat(chat_id=int(TELEGRAM_GROUP_ID)) & filters.TEXT,
            handle_all_messages
        ))
        
        application.add_handler(CallbackQueryHandler(handle_button_click))
        
        logger.info("✅ البوت يعمل ويراقب الجروب")
        logger.info("📡 جاهز لاستقبال رسائل SendPulse...")
        
        # بدء التشغيل
        application.run_polling()
        
    except Exception as e:
        logger.error(f"❌ خطأ فادح في التشغيل: {e}")

if __name__ == '__main__':
    main()
