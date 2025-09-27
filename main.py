from flask import Flask, request, jsonify
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
import os
import logging
import json
from datetime import datetime

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
    """تنسيق رسالة من بيانات SendPulse بناءً على المتغيرات المحددة"""
    try:
        if isinstance(data, dict):
            # استخراج المتغيرات حسب تنسيق SendPulse الذي ذكرته
            full_name = data.get('full_name', 'غير معروف')
            username = data.get('username', 'غير معروف')
            agent = data.get('Agent', 'غير معروف')
            price = data.get('PriceIN', 'غير معروف')
            amount_egp = data.get('much2', 'غير معروف')
            paid_by = data.get('PaidBy', 'غير معروف')
            insta_control = data.get('InstaControl', 'غير معروف')
            short_url = data.get('ShortUrl', 'غير معروف')
            amount_usd = data.get('much', 'غير معروف')
            platform = data.get('Platform', 'غير معروف')
            redid = data.get('redid', 'غير معروف')
            note = data.get('Note', '')
            
            # بناء الرسالة بنفس تنسيق SendPulse ولكن بشكل منظم
            message = f"""
🛒 **طلب جديد - SendPulse**

👤 **العميل:** {full_name}
📱 **تليجرام:** @{username}

📊 **تفاصيل الطلب:**
• شفت {agent} سعر البيع {price}
• المبلغ {amount_egp} جنيه {paid_by}
• إنستاباي باسم {insta_control}

🔗 **الرابط:** {short_url}
💰 **الرصيد:** {amount_usd} $ {platform}
🆔 **المعرف:** {redid}

{f"💡 **ملاحظة:** {note}" if note else ""}

⏰ **وقت الاستلام:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """.strip()
            
            return message
        else:
            # إذا كانت البيانات ليست JSON
            return f"🛒 **طلب SendPulse**\n\n{str(data)}\n\n⚡ **تم الاستلام تلقائياً**"
        
    except Exception as e:
        logger.error(f"خطأ في تنسيق الرسالة: {e}")
        return f"🔔 **طلب SendPulse**\n\n{str(data)}\n\n⚡ **تم الاستلام تلقائياً**"

@app.route('/')
def home():
    """الصفحة الرئيسية للتحقق من عمل الخادم"""
    return """
    <h1>🤖 SendPulse Telegram Bot</h1>
    <p>الخادم يعمل بشكل صحيح!</p>
    <p><strong>متغيرات SendPulse المدعومة:</strong></p>
    <ul>
        <li><code>full_name</code> - اسم العميل</li>
        <li><code>username</code> - اسم المستخدم في تليجرام</li>
        <li><code>Agent</code> - الوكيل/المنتج</li>
        <li><code>PriceIN</code> - سعر البيع</li>
        <li><code>much2</code> - المبلغ بالجنيه</li>
        <li><code>PaidBy</code> - طريقة الدفع</li>
        <li><code>InstaControl</code> - اسم إنستاباي</li>
        <li><code>ShortUrl</code> - الرابط المختصر</li>
        <li><code>much</code> - الرصيد بالدولار</li>
        <li><code>Platform</code> - المنصة</li>
        <li><code>redid</code> - المعرف</li>
        <li><code>Note</code> - ملاحظة</li>
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
            logger.info(f"📊 بيانات JSON مستلمة: {json.dumps(data, ensure_ascii=False)[:500]}...")
        else:
            # إذا كانت البيانات نصاً عادياً
            data = request.get_data(as_text=True)
            logger.info(f"📝 بيانات نصية: {data[:500]}...")
            
            # محاولة تحويل النص إلى JSON إذا كان بتنسيق JSON
            try:
                if data.strip().startswith('{'):
                    data = json.loads(data)
                    logger.info("✅ تم تحويل النص إلى JSON بنجاح")
            except:
                pass  # ابقى كـ نص إذا فشل التحويل
        
        if not data:
            logger.warning("⚠️ لا توجد بيانات في الطلب")
            return jsonify({"error": "No data received"}), 400
        
        # تنسيق الرسالة
        message_text = format_sendpulse_message(data)
        
        # إنشاء معرف للطلب
        order_id = "unknown"
        if isinstance(data, dict):
            order_id = data.get('redid', data.get('id', 'unknown'))
        
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
            "telegram_message_id": sent_message.message_id,
            "order_id": order_id
        }), 200
        
    except Exception as e:
        logger.error(f"❌ خطأ في معالجة webhook: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/test', methods=['POST', 'GET'])
def test_webhook():
    """لاختبار إرسال رسالة ببيانات مشابهة لـ SendPulse"""
    try:
        # بيانات اختبارية مطابقة لتنسيق SendPulse
        test_data = {
            "full_name": "أحمد محمد",
            "username": "ahmed2024",
            "Agent": "Ayman",
            "PriceIN": "50.5",
            "much2": "505",
            "PaidBy": "Vodafone",
            "InstaControl": "أحمد محمد",
            "ShortUrl": "https://goolnk.com/abc123",
            "much": "10.1",
            "Platform": "RedotPay",
            "redid": "123456789",
            "Note": "طلب عادي"
        }
        
        message_text = format_sendpulse_message(test_data)
        
        sent_message = bot.send_message(
            chat_id=TELEGRAM_GROUP_ID,
            text=message_text,
            reply_markup=create_order_keyboard(test_data['redid']),
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

@app.route('/test-raw', methods=['POST'])
def test_raw_data():
    """لاختبار بيانات خام كما تأتي من SendPulse"""
    try:
        # محاكاة البيانات كما تأتي من SendPulse
        raw_data = {
            "full_name": "{{full_name}}",
            "username": "{{username}}", 
            "Agent": "{{Agent}}",
            "PriceIN": "{{$PriceIN}}",
            "much2": "{{much2}}",
            "PaidBy": "{{PaidBy}}",
            "InstaControl": "{{InstaControl}}",
            "ShortUrl": "{{ShortUrl}}",
            "much": "{{much}}",
            "Platform": "{{Platform}}",
            "redid": "{{redid}}",
            "Note": "{{Note}}"
        }
        
        return jsonify({
            "description": "هذا هو تنسيق البيانات المتوقع من SendPulse",
            "expected_format": raw_data,
            "instructions": "عند إعداد webhook في SendPulse، تأكد من إرسال البيانات بهذا التنسيق"
        }), 200
        
    except Exception as e:
        logger.error(f"❌ خطأ في اختبار البيانات الخام: {e}")
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
        
        # اختبار الاتصال بالبوت
        try:
            bot_info = bot.get_me()
            logger.info(f"🤖 البوت: @{bot_info.username} (ID: {bot_info.id})")
        except Exception as e:
            logger.error(f"❌ خطأ في الاتصال بالبوت: {e}")
    else:
        logger.error("❌ لا يمكن تشغيل الخادم - متغيرات بيئية مفقودة")
    
    app.run(host='0.0.0.0', port=PORT, debug=False)
