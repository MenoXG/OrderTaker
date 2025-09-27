from flask import Flask, request, jsonify
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
import os
import logging
import json

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
PORT = int(os.environ.get('PORT', 8000))

# إنشاء كائن البوت
bot = Bot(token=BOT_TOKEN)

def create_order_keyboard(order_id):
    """إنشاء أزرار تفاعلية للطلبات"""
    keyboard = [
        [
            InlineKeyboardButton("✅ تأكيد الاستلام", callback_data=f"confirm_{order_id}"),
            InlineKeyboardButton("📞 تواصل مع العميل", callback_data=f"contact_{order_id}")
        ],
        [
            InlineKeyboardButton("⚠️ بلاغ مشكلة", callback_data=f"problem_{order_id}"),
            InlineKeyboardButton("⏱ تأجيل المعالجة", callback_data=f"delay_{order_id}")
        ],
        [
            InlineKeyboardButton("💰 تأكيد التحويل", callback_data=f"payment_{order_id}"),
            InlineKeyboardButton("🎯 تم الإكمال", callback_data=f"complete_{order_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def format_sendpulse_message(data):
    """تنسيق رسالة من بيانات SendPulse"""
    try:
        # إذا كانت البيانات تحتوي على النص مباشرة (للتجربة)
        if isinstance(data, str):
            return f"🛒 **طلب SendPulse**\n\n{data}\n\n⚡ **تم الاستلام تلقائياً**"
        
        # إذا كانت البيانات كـ JSON object
        if isinstance(data, dict):
            # محاولة استخراج الحقول الشائعة
            customer_name = data.get('customer_name', data.get('client', data.get('عميل', 'غير معروف')))
            product = data.get('product', data.get('منتج', data.get('شفت', 'غير معروف')))
            amount = data.get('amount', data.get('مبلغ', data.get('سعر', 'غير معروف')))
            payment_method = data.get('payment_method', data.get('طريقة الدفع', 'غير معروف'))
            order_id = data.get('order_id', data.get('id', data.get('معرف', 'غير معروف')))
            
            message = f"""
🛒 **طلب جديد من SendPulse**

👤 **العميل:** {customer_name}
📦 **المنتج:** {product}
💵 **المبلغ:** {amount}
🏦 **طريقة الدفع:** {payment_method}
🆔 **رقم الطلب:** {order_id}

⚡ **تم الاستلام تلقائياً**
            """.strip()
            
            return message
        
        # إذا كانت البيانات بأي شكل آخر
        return f"🛒 **طلب SendPulse**\n\n{json.dumps(data, ensure_ascii=False, indent=2)}\n\n⚡ **تم الاستلام تلقائياً**"
        
    except Exception as e:
        logger.error(f"خطأ في تنسيق الرسالة: {e}")
        return f"🔔 **طلب SendPulse**\n\n{str(data)}\n\n⚡ **تم الاستلام تلقائياً**"

@app.route('/')
def home():
    """الصفحة الرئيسية للتحقق من عمل الخادم"""
    return """
    <h1>🤖 SendPulse Telegram Bot</h1>
    <p>الخادم يعمل بشكل صحيح!</p>
    <p>Endpoints المتاحة:</p>
    <ul>
        <li><code>POST /webhook/sendpulse</code> - لاستقبال إشعارات SendPulse</li>
        <li><code>GET /health</code> - للتحقق من صحة الخادم</li>
        <li><code>POST /test</code> - لاختبار إرسال رسالة</li>
    </ul>
    """

@app.route('/health')
def health_check():
    """للتحقق من صحة الخادم"""
    return jsonify({
        "status": "healthy",
        "service": "SendPulse Telegram Bot",
        "bot_ready": bool(BOT_TOKEN and TELEGRAM_GROUP_ID)
    })

@app.route('/webhook/sendpulse', methods=['POST'])
def sendpulse_webhook():
    """استقبال إشعارات SendPulse"""
    try:
        # تسجيل وصول الطلب
        logger.info("📨 تم استلام webhook من SendPulse")
        
        # الحصول على البيانات من SendPulse
        content_type = request.content_type.lower()
        
        if content_type == 'application/json':
            data = request.get_json()
            logger.info(f"📊 بيانات JSON: {json.dumps(data, ensure_ascii=False)[:500]}...")
        else:
            # إذا كانت البيانات نصاً عادياً
            data = request.get_data(as_text=True)
            logger.info(f"📝 بيانات نصية: {data[:500]}...")
        
        if not data:
            logger.warning("⚠️ لا توجد بيانات في الطلب")
            return jsonify({"error": "No data received"}), 400
        
        # تنسيق الرسالة
        message_text = format_sendpulse_message(data)
        
        # إنشاء معرف للطلب (يمكن تعديله حسب بيانات SendPulse)
        order_id = "unknown"
        if isinstance(data, dict) and 'order_id' in data:
            order_id = data['order_id']
        elif isinstance(data, dict) and 'id' in data:
            order_id = data['id']
        
        # إرسال الرسالة إلى مجموعة التليجرام
        sent_message = bot.send_message(
            chat_id=TELEGRAM_GROUP_ID,
            text=message_text,
            reply_markup=create_order_keyboard(order_id),
            parse_mode='Markdown'
        )
        
        logger.info(f"✅ تم إرسال الرسالة إلى التليجرام (ID: {sent_message.message_id})")
        
        return jsonify({
            "status": "success",
            "message": "Notification sent to Telegram",
            "telegram_message_id": sent_message.message_id
        }), 200
        
    except Exception as e:
        logger.error(f"❌ خطأ في معالجة webhook: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/test', methods=['POST', 'GET'])
def test_webhook():
    """لاختبار إرسال رسالة"""
    try:
        # بيانات اختبارية
        test_data = {
            "customer_name": "عميل اختباري",
            "product": "منتج اختباري",
            "amount": "100 جنيه",
            "payment_method": "Vodafone",
            "order_id": "TEST-001",
            "timestamp": "2024-01-01 12:00:00"
        }
        
        message_text = format_sendpulse_message(test_data)
        
        sent_message = bot.send_message(
            chat_id=TELEGRAM_GROUP_ID,
            text=message_text,
            reply_markup=create_order_keyboard("TEST-001"),
            parse_mode='Markdown'
        )
        
        logger.info("✅ تم إرسال رسالة الاختبار بنجاح")
        
        return jsonify({
            "status": "success",
            "message": "Test notification sent",
            "test_data": test_data
        }), 200
        
    except Exception as e:
        logger.error(f"❌ خطأ في اختبار webhook: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/webhook/telegram', methods=['POST'])
def telegram_webhook():
    """للاستقبال من Telegram إذا أردنا استخدام webhook للبوت"""
    try:
        update_data = request.get_json()
        logger.info(f"📱 تحديث من Telegram: {update_data}")
        
        # هنا يمكنك إضافة معالجة للأزرار إذا استخدمنا webhook للبوت
        if 'callback_query' in update_data:
            callback_data = update_data['callback_query']['data']
            message_id = update_data['callback_query']['message']['message_id']
            user_name = update_data['callback_query']['from'].get('first_name', 'مستخدم')
            
            logger.info(f"🔘 زر مضغوط: {callback_data} بواسطة {user_name}")
            
            # تحديث الرسالة
            bot.edit_message_text(
                chat_id=TELEGRAM_GROUP_ID,
                message_id=message_id,
                text=f"الرسالة الأصلية\n\n✅ تم التعامل: {callback_data}\n👤 بواسطة: {user_name}",
                parse_mode='Markdown'
            )
        
        return jsonify({"status": "ok"}), 200
        
    except Exception as e:
        logger.error(f"❌ خطأ في webhook Telegram: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # التحقق من المتغيرات البيئية
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN غير مضبوط!")
    if not TELEGRAM_GROUP_ID:
        logger.error("❌ TELEGRAM_GROUP_ID غير مضبوط!")
    
    if BOT_TOKEN and TELEGRAM_GROUP_ID:
        logger.info("🚀 بدء تشغيل خادم SendPulse Webhook...")
        logger.info(f"🌐 الخادم يعمل على المنفذ: {PORT}")
        logger.info("📡 جاهز لاستقبال إشعارات SendPulse...")
    else:
        logger.error("❌ لا يمكن تشغيل الخادم - متغيرات بيئية مفقودة")
    
    app.run(host='0.0.0.0', port=PORT, debug=False)
