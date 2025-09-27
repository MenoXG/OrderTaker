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
    """معالجة جميع الرسائل في الجروب - مع تركيز خاص على رسائل القنوات"""
    try:
        message = update.message
        
        if not message:
            return
        
        # تسجيل مفصل للمعلومات
        logger.info("=" * 50)
        logger.info(f"📨 رسالة مستلمة - ID: {message.message_id}")
        logger.info(f"💬 نوع المحتوى: {message.content_type if hasattr(message, 'content_type') else 'Unknown'}")
        
        # معلومات المرسل - هذا هو الجزء المهم!
        if message.from_user:
            logger.info(f"👤 مرسل عادي: {message.from_user.first_name} (ID: {message.from_user.id})")
        elif hasattr(message, 'sender_chat') and message.sender_chat:
            logger.info(f"📡 مرسل قناة: {message.sender_chat.title} (ID: {message.sender_chat.id})")
            logger.info(f"🔗 نوع القناة: {message.sender_chat.type}")
        else:
            logger.info("🔍 مرسل مجهول المصدر")
        
        # الحصول على النص
        message_text = ""
        if message.text:
            message_text = message.text
            logger.info(f"📝 النص الكامل: {message_text}")
        elif message.caption:
            message_text = message.caption
            logger.info(f"🏷️ التسمية: {message_text}")
        else:
            logger.info("❌ لا يوجد نص أو تسمية")
            return
        
        # تجاهل الرسائل من البوت نفسه
        bot_user = await context.bot.get_me()
        if message.from_user and message.from_user.id == bot_user.id:
            logger.info("🚫 تجاهل رسالة من البوت نفسه")
            return
        
        # كلمات SendPulse المفتاحية المحدثة
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
            "الحميل",  # من الصورة
            "RedotPay",
            "Binance",
            "Bybit",   # من الصورة
            "السبع",   # من الصورة
            "تحويل من",
            "رقم/اسم المحفظة"
        ]
        
        # البحث عن كلمات SendPulse
        found_keywords = []
        for keyword in sendpulse_keywords:
            if keyword in message_text:
                found_keywords.append(keyword)
        
        if found_keywords:
            logger.info(f"✅ كلمات SendPulse المكتشفة: {found_keywords}")
            is_sendpulse = True
        else:
            logger.info("🚫 لم يتم العثور على كلمات SendPulse")
            is_sendpulse = False
        
        # إذا كانت الرسالة من قناة، نعتبرها SendPulse تلقائياً (بناءً على الصورة)
        if hasattr(message, 'sender_chat') and message.sender_chat:
            logger.info("🎯 رسالة من قناة - نعتبرها SendPulse")
            is_sendpulse = True
        
        if not is_sendpulse:
            logger.info("🚫 ليست رسالة SendPulse - تم تجاهلها")
            return
        
        logger.info("🎉 تم التعرف على رسالة SendPulse!")
        
        # تنسيق الرسالة بشكل منظم
        formatted_message = format_sendpulse_message(message_text)
        
        # إعادة إرسال الرسالة مع الأزرار
        sent_message = await context.bot.send_message(
            chat_id=TELEGRAM_GROUP_ID,
            text=formatted_message,
            reply_markup=create_keyboard(),
            parse_mode='Markdown'
        )
        
        logger.info(f"✅ تم إعادة إرسال الرسالة بنجاح - ID الجديد: {sent_message.message_id}")
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"❌ خطأ في معالجة الرسالة: {e}")
        import traceback
        logger.error(traceback.format_exc())

def format_sendpulse_message(text):
    """تنسيق رسالة SendPulse بشكل منظم"""
    try:
        # إذا كان النص قصيراً، نرجعه كما هو
        if len(text) < 50:
            return f"🛒 **طلب SendPulse**\n\n{text}\n\n⚡ **تم التوجيه تلقائياً**"
        
        # محاولة استخراج المعلومات الرئيسية
        lines = text.split('\n')
        important_lines = []
        
        for line in lines:
            line = line.strip()
            if any(keyword in line for keyword in [
                'SendPulse', 'الحميل', 'العميل', 'سعر البيع', 'شفت', 
                'جنيه', 'goolnk.com', 'الرصيد', 'Vodafone', 'Instapay',
                'RedotPay', 'Binance', 'Bybit'
            ]):
                important_lines.append(line)
        
        if important_lines:
            formatted_text = "\n".join(important_lines)
        else:
            formatted_text = text
        
        return f"🛒 **طلب SendPulse**\n\n{formatted_text}\n\n⚡ **تم التوجيه تلقائياً**"
        
    except Exception as e:
        logger.error(f"❌ خطأ في تنسيق الرسالة: {e}")
        return f"🔔 **طلب SendPulse**\n\n{text}\n\n⚡ **تم التوجيه تلقائياً**"

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
        
        logger.info(f"✅ تم تحديث الرسالة بالإجراء: {action}")
        
    except Exception as e:
        logger.error(f"❌ خطأ في معالجة الزر: {e}")

def main():
    """الدالة الرئيسية"""
    try:
        if not BOT_TOKEN or not TELEGRAM_GROUP_ID:
            logger.error("❌ متغيرات بيئية مفقودة")
            return
        
        logger.info("🚀 بدء تشغيل البوت...")
        logger.info(f"📊 إعدادات البوت:")
        logger.info(f"   - BOT_TOKEN: {'✅ مضبوط' if BOT_TOKEN else '❌ مفقود'}")
        logger.info(f"   - TELEGRAM_GROUP_ID: {'✅ مضبوط' if TELEGRAM_GROUP_ID else '❌ مفقود'}")
        
        # إنشاء التطبيق
        application = Application.builder().token(BOT_TOKEN).build()
        
        # اختبار اتصال البوت
        bot_info = await application.bot.get_me()
        logger.info(f"🤖 البوت: @{bot_info.username} (ID: {bot_info.id})")
        
        # إضافة handlers - نراقب جميع أنواع المحتوى
        application.add_handler(MessageHandler(
            filters.Chat(chat_id=int(TELEGRAM_GROUP_ID)) & 
            (filters.TEXT | filters.CAPTION | filters.PHOTO | filters.Document.ALL),
            handle_all_messages
        ))
        
        application.add_handler(CallbackQueryHandler(handle_button_click))
        
        logger.info("✅ تم إعداد البوت بنجاح")
        logger.info("📡 البوت يراقب الجروب لرسائل SendPulse من القنوات...")
        
        # بدء التشغيل
        application.run_polling()
        
    except Exception as e:
        logger.error(f"❌ خطأ فادح في التشغيل: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == '__main__':
    main()
