from flask import Flask, request, jsonify
import os
import logging
import requests
import time

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

@app.route('/')
def home():
    """الصفحة الرئيسية مع معلومات التطبيق"""
    try:
        # فحص حالة التطبيق
        status = {
            "status": "running",
            "service": "SendPulse Telegram Bot",
            "timestamp": time.time(),
            "environment": {
                "bot_token_set": bool(BOT_TOKEN),
                "group_id_set": bool(TELEGRAM_GROUP_ID),
                "port": PORT
            }
        }
        logger.info("✅ تم استلام طلب على الصفحة الرئيسية")
        return jsonify(status)
    except Exception as e:
        logger.error(f"❌ خطأ في الصفحة الرئيسية: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/health')
def health():
    """Health check للمراقبة"""
    try:
        # فحوصات أساسية
        checks = {
            "flask_app": True,
            "environment_variables": bool(BOT_TOKEN and TELEGRAM_GROUP_ID),
            "timestamp": time.time()
        }
        
        # فحص الاتصال بالتليجرام (اختياري)
        if BOT_TOKEN:
            try:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
                response = requests.get(url, timeout=5)
                checks["telegram_connection"] = response.status_code == 200
            except:
                checks["telegram_connection"] = False
        else:
            checks["telegram_connection"] = False
        
        # تحديد الحالة العامة
        all_checks_passed = all(checks.values())
        status = "healthy" if all_checks_passed else "degraded"
        
        result = {
            "status": status,
            "checks": checks,
            "timestamp": time.time()
        }
        
        logger.info(f"✅ Health check: {status}")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"❌ خطأ في health check: {e}")
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

@app.route('/test')
def test():
    """صفحة اختبار بسيطة"""
    return "✅ SendPulse Bot is working!"

@app.route('/webhook/sendpulse', methods=['GET', 'POST'])
def sendpulse_webhook():
    """Webhook لاستقبال إشعارات SendPulse"""
    try:
        if request.method == 'GET':
            return jsonify({
                "message": "SendPulse webhook is ready",
                "instructions": "Send POST requests with JSON data",
                "expected_format": {
                    "full_name": "اسم العميل",
                    "username": "اسم المستخدم",
                    "Agent": "المنتج",
                    "PriceIN": "السعر",
                    "much2": "المبلغ بالجنيه",
                    "PaidBy": "طريقة الدفع",
                    "InstaControl": "اسم إنستاباي",
                    "ShortUrl": "الرابط",
                    "much": "الرصيد بالدولار",
                    "Platform": "المنصة",
                    "redid": "المعرف",
                    "Note": "ملاحظة"
                }
            })
        
        # معالجة طلبات POST
        logger.info("📨 تم استلام webhook من SendPulse")
        
        # الحصول على البيانات
        data = request.get_json(silent=True) or request.get_data(as_text=True)
        logger.info(f"📊 البيانات المستلمة: {str(data)[:200]}...")
        
        if not BOT_TOKEN or not TELEGRAM_GROUP_ID:
            return jsonify({"error": "Bot not configured"}), 500
        
        # إرسال رسالة إلى التليجرام
        message_text = format_message(data)
        
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_GROUP_ID,
            "text": message_text,
            "parse_mode": "Markdown"
        }
        
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            logger.info("✅ تم إرسال الرسالة إلى التليجرام")
            return jsonify({
                "status": "success",
                "message": "Notification sent to Telegram"
            })
        else:
            logger.error(f"❌ خطأ من التليجرام: {response.text}")
            return jsonify({"error": response.text}), 500
            
    except Exception as e:
        logger.error(f"❌ خطأ في webhook: {e}")
        return jsonify({"error": str(e)}), 500

def format_message(data):
    """تنسيق الرسالة"""
    if isinstance(data, dict):
        # استخدام البيانات من SendPulse
        full_name = data.get('full_name', 'غير معروف')
        product = data.get('Agent', 'غير معروف')
        amount = data.get('much2', 'غير معروف')
        
        return f"""
🛒 **طلب جديد من SendPulse**

👤 **العميل:** {full_name}
📦 **المنتج:** {product}
💵 **المبلغ:** {amount} جنيه

⏰ **الوقت:** {time.strftime('%Y-%m-%d %H:%M:%S')}
        """.strip()
    else:
        return f"🛒 **طلب SendPulse**\n\n{data}"

if __name__ == '__main__':
    # تسجيل بدء التشغيل
    logger.info("=" * 50)
    logger.info("🚀 بدء تشغيل SendPulse Bot")
    logger.info(f"🔧 PORT: {PORT}")
    logger.info(f"🔧 BOT_TOKEN: {'✅ مضبوط' if BOT_TOKEN else '❌ مفقود'}")
    logger.info(f"🔧 TELEGRAM_GROUP_ID: {'✅ مضبوط' if TELEGRAM_GROUP_ID else '❌ مفقود'}")
    logger.info("=" * 50)
    
    try:
        app.run(host='0.0.0.0', port=PORT, debug=False)
    except Exception as e:
        logger.error(f"❌ فشل في تشغيل التطبيق: {e}")
        raise
