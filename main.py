import os
import logging
from flask import Flask, request, jsonify
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import asyncio
from threading import Thread

# إعداد logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# متغيرات البيئة
BOT_TOKEN = os.environ.get('BOT_TOKEN')
TELEGRAM_GROUP_ID = os.environ.get('TELEGRAM_GROUP_ID')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
PORT = int(os.environ.get('PORT', 8000))

# تخزين البوت والتطبيق كمتغيرات عامة
bot = None
application = None

def create_keyboard():
    """إنشاء لوحة الأزرار التفاعلية"""
    keyboard = [
        [
            InlineKeyboardButton("✅ تم التعامل", callback_data="handled"),
            InlineKeyboardButton("⏱ مؤجل", callback_data="postponed")
        ],
        [
            InlineKeyboardButton("📞 اتصل بالعميل", callback_data="call_customer"),
            InlineKeyboardButton("📧 إرسال بريد", callback_data="send_email")
        ],
        [
            InlineKeyboardButton("👀 تحت المراجعة", callback_data="under_review"),
            InlineKeyboardButton("❌ إلغاء", callback_data="cancelled")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def send_telegram_message(message_text, message_id=None):
    """إرسال رسالة إلى الجروب مع الأزرار"""
    try:
        if not TELEGRAM_GROUP_ID:
            logger.error("TELEGRAM_GROUP_ID not set")
            return
        
        # إضافة معلومات إضافية للرسالة
        formatted_message = f"📋 طلب جديد\n\n{message_text}\n\n🆔 رقم الطلب: {message_id or 'N/A'}"
        
        await bot.send_message(
            chat_id=TELEGRAM_GROUP_ID,
            text=formatted_message,
            reply_markup=create_keyboard(),
            parse_mode='HTML'
        )
        logger.info("Message sent to Telegram group successfully")
        
    except Exception as e:
        logger.error(f"Error sending message to Telegram: {e}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الضغط على الأزرار"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    button_data = query.data
    
    # ردود مختلفة لكل زر
    responses = {
        "handled": "✅ تم التعامل مع الطلب",
        "postponed": "⏱ تم تأجيل الطلب",
        "call_customer": "📞 سيتم الاتصال بالعميل",
        "send_email": "📧 سيتم إرسال البريد",
        "under_review": "👀 الطلب تحت المراجعة",
        "cancelled": "❌ تم إلغاء الطلب"
    }
    
    response_text = responses.get(button_data, "إجراء غير معروف")
    
    # تحديث الرسالة الأصلية لإضافة المعلومات
    original_text = query.message.text
    new_text = f"{original_text}\n\n---\n🔹 {response_text}\n👤 بواسطة: {user.first_name}"
    
    await query.edit_message_text(
        text=new_text,
        reply_markup=None,  # إزالة الأزرار بعد الاختيار
        parse_mode='HTML'
    )
    
    logger.info(f"User {user.id} selected: {button_data}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر البدء"""
    await update.message.reply_text(
        "مرحباً! أنا بوت إشعارات SendPulse. أنتظر استلام الطلبات..."
    )

async def setup_bot():
    """إعداد البوت والتطبيق"""
    global bot, application
    
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set in environment variables")
        return
    
    # إنشاء تطبيق البوت
    application = Application.builder().token(BOT_TOKEN).build()
    bot = application.bot
    
    # إضافة handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # إعداد webhook
    await application.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    logger.info("Webhook set successfully")

@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    """Webhook لاستقبال تحديثات تليجرام"""
    try:
        # معالجة التحديث في thread منفصل
        thread = Thread(target=asyncio.run, args=(handle_telegram_update(request),))
        thread.start()
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Error in webhook: {e}")
        return jsonify({"error": str(e)}), 500

async def handle_telegram_update(request):
    """معالجة تحديث تليجرام"""
    try:
        update = Update.de_json(request.get_json(), application.bot)
        await application.process_update(update)
    except Exception as e:
        logger.error(f"Error processing update: {e}")

@app.route('/sendpulse-webhook', methods=['POST'])
def sendpulse_webhook():
    """Webhook لاستقبال إشعارات SendPulse"""
    try:
        data = request.get_json()
        logger.info(f"Received SendPulse data: {data}")
        
        if not data:
            return jsonify({"error": "No data received"}), 400
        
        # استخراج معلومات الطلب من بيانات SendPulse
        message_text = format_sendpulse_message(data)
        message_id = data.get('id') or data.get('order_id')
        
        # إرسال الرسالة إلى التليجرام
        asyncio.run(send_telegram_message(message_text, message_id))
        
        return jsonify({"status": "Message processed"}), 200
        
    except Exception as e:
        logger.error(f"Error processing SendPulse webhook: {e}")
        return jsonify({"error": str(e)}), 500

def format_sendpulse_message(data):
    """تنسيق رسالة SendPulse لعرضها بشكل منظم"""
    try:
        # تنسيق أساسي - يمكنك تعديله حسب هيكل بيانات SendPulse
        customer_name = data.get('customer_name', 'غير معروف')
        customer_email = data.get('customer_email', 'غير معروف')
        customer_phone = data.get('customer_phone', 'غير معروف')
        order_details = data.get('order_details', 'لا توجد تفاصيل')
        order_amount = data.get('amount', 'غير معروف')
        
        formatted_message = f"""
👤 **العميل:** {customer_name}
📧 **البريد:** {customer_email}
📞 **الهاتف:** {customer_phone}
💵 **المبلغ:** {order_amount}
📋 **تفاصيل الطلب:**
{order_details}
        """
        
        return formatted_message.strip()
        
    except Exception as e:
        logger.error(f"Error formatting message: {e}")
        return str(data)

@app.route('/health', methods=['GET'])
def health_check():
    """فحص صحة التطبيق"""
    return jsonify({"status": "healthy", "service": "SendPulse Telegram Bot"})

@app.route('/test-message', methods=['POST'])
def test_message():
    """إرسال رسالة تجريبية"""
    try:
        test_data = {
            "customer_name": "عميل تجريبي",
            "customer_email": "test@example.com",
            "customer_phone": "+1234567890",
            "order_details": "هذا طلب تجريبي للاختبار",
            "amount": "100 ريال"
        }
        
        message_text = format_sendpulse_message(test_data)
        asyncio.run(send_telegram_message(message_text, "TEST-001"))
        
        return jsonify({"status": "Test message sent"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

async def main():
    """الدالة الرئيسية"""
    await setup_bot()

def run_bot():
    """تشغيل البوت في thread منفصل"""
    asyncio.run(main())

if __name__ == '__main__':
    # تشغيل إعداد البوت عند البدء
    thread = Thread(target=run_bot)
    thread.start()
    
    # تشغيل Flask app
    app.run(host='0.0.0.0', port=PORT, debug=False)
