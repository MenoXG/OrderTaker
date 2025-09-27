import os
import logging
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
        
        # إذا لم تكن هناك رسالة
        if not message:
            return
        
        # تسجيل أساسي للمرسل
        sender_info = "Unknown"
        if message.from_user:
            sender_info = f"{message.from_user.first_name} (User)"
        elif message.sender_chat:
            sender_info = f"{message.sender_chat.title} (Channel)"
        
        logger.info(f"📨 رسالة من: {sender_info}")
        
        # الحصول على النص
        message_text = ""
        if message.text:
            message_text = message.text
        elif message.caption:
            message_text = message.caption
        
        logger.info(f"💬 النص: {message_text[:100]}...")
        
        # تجاهل الرسائل من البوت نفسه
        bot_user = await context.bot.get_me()
        if message.from_user and message.from_user.id == bot_user.id:
            logger.info("🚫 تجاهل رسالة من البوت نفسه")
            return
        
        # كلمات SendPulse المفتاحية (محدثة بناءً على الصورة)
        sendpulse_keywords = [
            "SendPulse Notifications",
            "سعر البيع",
            "شفت",
            "جنيه", 
            "goolnk.com",
            "الرصيد",
            "Vodafone",
            "Instapay",
            "للبحرام",
            "الحميل",  # كلمة جديدة من الصورة
            "RedotPay",
            "Binance",
            "Bybit"   # كلمة جديدة من الصورة
        ]
        
        # التحقق من رسالة SendPulse
        is_sendpulse = False
        if message_text:
            for keyword in sendpulse_keywords:
                if keyword in message_text:
                    is_sendpulse = True
                    logger.info(f"✅ وجدت كلمة مفتاحية: {keyword}")
                    break
        
        if not is_sendpulse:
            logger.info("🚫 ليست رسالة SendPulse - تم تجاهلها")
            return
        
        logger.info("🎯 تم التعرف على رسالة SendPulse!")
        
        # تنسيق بسيط للرسالة
        formatted_message = f"🛒 **طلب SendPulse**\n\n{message_text}\n\n⚡ **تم التوجيه تلقائياً**"
        
        # إعادة الإرسال مع الأزرار
        await context.bot.send_message(
            chat_id=TELEGRAM_GROUP_ID,
            text=formatted_message,
            reply_markup=create_keyboard(),
            parse_mode='Markdown'
        )
        
        logger.info("✅ تم إعادة إرسال رسالة SendPulse بنجاح")
        
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
        if not BOT_TOKEN or not TELEGRAM_GROUP_ID:
            logger.error("❌ متغيرات بيئية مفقودة")
            return
        
        logger.info("🚀 بدء تشغيل البوت...")
        
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
        logger.error(f"❌ خطأ: {e}")

if __name__ == '__main__':
    main()
