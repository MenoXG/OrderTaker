import os
import logging
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, CallbackQueryHandler, ContextTypes

# إعداد logging مفصل
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
    """معالجة جميع الرسائل في الجروب بما فيها رسائل القنوات والبوتات"""
    try:
        message = update.message
        
        # تسجيل تفصيلي
        logger.info(f"📨 رسالة مستلمة - ID: {message.message_id}")
        
        # معلومات المرسل
        if message.from_user:
            sender_info = f"{message.from_user.first_name} (ID: {message.from_user.id})"
        else:
            sender_info = "Channel/Bot (No user info)"
        logger.info(f"👤 من: {sender_info}")
        
        # محتوى الرسالة
        if message.text:
            message_content = message.text
            logger.info(f"💬 نص الرسالة: {message_content[:200]}...")
        elif message.caption:
            message_content = message.caption
            logger.info(f"📝 شرح الرسالة: {message_content[:200]}...")
        else:
            message_content = ""
            logger.info("📎 رسالة بدون نص أو شرح")
        
        # تجاهل الرسائل من البوت نفسه
        bot_user = await context.bot.get_me()
        if message.from_user and message.from_user.id == bot_user.id:
            logger.info("🚫 تجاهل رسالة من البوت نفسه")
            return
        
        # تحديد إذا كانت الرسالة من SendPulse Notifications
        is_sendpulse = False
        
        if message_content:
            # تحقق إذا كانت الرسالة تحتوي على علامات SendPulse
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
                "العميل"
            ]
            
            for keyword in sendpulse_keywords:
                if keyword in message_content:
                    is_sendpulse = True
                    logger.info(f"✅ تم التعرف على رسالة SendPulse (كلمة مفتاحية: {keyword})")
                    break
        
        # إذا لم تكن رسالة SendPulse، نتجاهلها
        if not is_sendpulse:
            logger.info("🚫 ليست رسالة SendPulse - تم تجاهلها")
            return
        
        # تنسيق رسالة SendPulse بشكل منظم
        formatted_message = format_sendpulse_message(message_content)
        
        # إعادة إرسال الرسالة مع الأزرار
        await context.bot.send_message(
            chat_id=TELEGRAM_GROUP_ID,
            text=formatted_message,
            reply_markup=create_keyboard(),
            parse_mode='Markdown'
        )
        
        logger.info("✅ تم إعادة إرسال رسالة SendPulse مع الأزرار")
        
    except Exception as e:
        logger.error(f"❌ خطأ في معالجة الرسالة: {e}")

def format_sendpulse_message(original_text):
    """تنسيق رسالة SendPulse بشكل منظم"""
    try:
        # إذا كان النص قصيراً، نرجعه كما هو مع تنسيق بسيط
        if len(original_text) < 100:
            return f"🛒 **طلب SendPulse**\n\n{original_text}\n\n⚡ **تم إعادة التوجيه تلقائياً**"
        
        # تقسيم النص إلى أسطر
        lines = original_text.split('\n')
        
        # استخراج المعلومات
        client_info = ""
        product_info = ""
        amount_info = ""
        payment_info = ""
        link_info = ""
        balance_info = ""
        id_info = ""
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if 'للبحرام' in line or 'العميل' in line:
                client_info = line
            elif 'شفت' in line or 'سعر البيع' in line:
                product_info = line
            elif 'جنيه' in line:
                amount_info = line
            elif 'Vodafone' in line or 'Instapay' in line:
                payment_info = line
            elif 'goolnk.com' in line:
                link_info = line
            elif 'الرصيد' in line:
                balance_info = line
            elif line.isdigit() and len(line) >= 9:  # معرف الدفع
                id_info = line
        
        # بناء الرسالة المنظمة
        formatted = "🛒 **طلب جديد - SendPulse**\n\n"
        
        if client_info:
            formatted += f"👤 **العميل:** {client_info}\n"
        if product_info:
            formatted += f"📦 **المنتج:** {product_info}\n"
        if amount_info:
            formatted += f"💵 **المبلغ:** {amount_info}\n"
        if payment_info:
            formatted += f"🏦 **طريقة الدفع:** {payment_info}\n"
        if link_info:
            formatted += f"🔗 **الرابط:** {link_info}\n"
        if balance_info:
            formatted += f"💰 **الرصيد:** {balance_info}\n"
        if id_info:
            formatted += f"🆔 **المعرف:** {id_info}\n"
        
        formatted += "\n⚡ **تم إعادة التوجيه تلقائياً**"
        
        return formatted
        
    except Exception as e:
        logger.error(f"❌ خطأ في تنسيق الرسالة: {e}")
        return f"🔔 **طلب SendPulse**\n\n{original_text}\n\n⚡ **تم إعادة التوجيه تلقائياً**"

async def handle_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة النقر على الأزرار"""
    try:
        query = update.callback_query
        await query.answer()
        
        user = query.from_user
        action = query.data
        
        logger.info(f"🔘 زر مضغوط: {action} بواسطة {user.first_name}")
        
        # ردود الإجراءات
        actions = {
            "done": "✅ تم التعامل مع الطلب",
            "later": "⏱ تم تأجيل الطلب", 
            "call": "📞 سيتم الاتصال بالعميل",
            "delete": "🗑 تم حذف الطلب"
        }
        
        response_text = actions.get(action, f"الإجراء: {action}")
        
        # تحديث الرسالة
        new_text = f"{query.message.text}\n\n---\n{response_text}\n👤 **المسؤول:** {user.first_name}"
        
        await query.edit_message_text(
            text=new_text,
            reply_markup=None,
            parse_mode='Markdown'
        )
        
        logger.info(f"✅ تم تحديث الرسالة بالإجراء: {action}")
        
    except Exception as e:
        logger.error(f"❌ خطأ في معالجة الزر: {e}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /start للتحقق من عمل البوت"""
    await update.message.reply_text(
        "🤖 البوت يعمل! جاهز لمراقبة رسائل SendPulse وإعادة توجيهها مع الأزرار."
    )
    logger.info("✅ تم استلام أمر /start")

def main():
    """الدالة الرئيسية"""
    try:
        # التحقق النهائي من المتغيرات
        if not BOT_TOKEN or not TELEGRAM_GROUP_ID:
            logger.error("❌ لا يمكن تشغيل البوت - متغيرات بيئية مفقودة")
            return
        
        logger.info("🚀 بدء إعداد البوت...")
        
        # إنشاء التطبيق
        application = Application.builder().token(BOT_TOKEN).build()
        
        # إضافة handlers - نستخدم الفلاتر الصحيحة
        # filters.TEXT للرسائل النصية، وسنعالج باقي الأنواع في الدالة
        application.add_handler(MessageHandler(
            filters.Chat(chat_id=int(TELEGRAM_GROUP_ID)) & filters.TEXT,
            handle_all_messages
        ))
        
        application.add_handler(CallbackQueryHandler(handle_button_click))
        application.add_handler(MessageHandler(filters.Command("start"), start_command))
        
        logger.info("✅ تم إعداد البوت بنجاح")
        logger.info("👂 البوت يستمع لرسائل SendPulse النصية في الجروب...")
        
        # بدء الاستماع
        application.run_polling()
        
    except Exception as e:
        logger.error(f"❌ خطأ فادح في التشغيل: {e}")

if __name__ == '__main__':
    main()
