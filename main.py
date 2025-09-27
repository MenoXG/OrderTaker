from flask import Flask, request, jsonify
import os
import logging
import requests

# إعداد logging مبسط
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# متغيرات البيئة
BOT_TOKEN = os.environ.get('BOT_TOKEN')
TELEGRAM_GROUP_ID = os.environ.get('TELEGRAM_GROUP_ID')
PORT = int(os.environ.get('PORT', 8000))

@app.route('/')
def home():
    logger.info("✅ تم استلام طلب على الصفحة الرئيسية")
    return jsonify({
        "status": "running",
        "service": "SendPulse Telegram Bot",
        "bot_token_set": bool(BOT_TOKEN),
        "group_id_set": bool(TELEGRAM_GROUP_ID)
    })

@app.route('/health')
def health():
    logger.info("✅ تم استعلام عن الصحة")
    return jsonify({"status": "healthy"})

@app.route('/test-telegram')
def test_telegram():
    """اختبار إرسال رسالة إلى التليجرام"""
    try:
        if not BOT_TOKEN or not TELEGRAM_GROUP_ID:
            return jsonify({"error": "Missing environment variables"}), 400
        
        # إرسال رسالة اختبارية باستخدام requests مباشرة
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_GROUP_ID,
            "text": "🤖 اختبار: البوت يعمل بنجاح!",
            "parse_mode": "Markdown"
        }
        
        response = requests.post(url, json=payload)
        logger.info(f"📤 رد التليجرام: {response.status_code}")
        
        if response.status_code == 200:
            return jsonify({"status": "success", "message": "Test message sent"})
        else:
            return jsonify({"error": response.text}), 500
            
    except Exception as e:
        logger.error(f"❌ خطأ في اختبار التليجرام: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/webhook/sendpulse', methods=['POST'])
def sendpulse_webhook():
    """استقبال إشعارات SendPulse (إصدار مبسط)"""
    try:
        logger.info("📨 تم استلام webhook من SendPulse")
        
        # تسجيل البيانات المستلمة
        data = request.get_json() or request.get_data(as_text=True)
        logger.info(f"📊 البيانات المستلمة: {str(data)[:500]}...")
        
        if not BOT_TOKEN or not TELEGRAM_GROUP_ID:
            return jsonify({"error": "Bot not configured"}), 500
        
        # إرسال رسالة مبسطة إلى التليجرام
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        
        # تنسيق الرسالة
        if isinstance(data, dict):
            message_text = f"🛒 طلب جديد\n\n{data}"
        else:
            message_text = f"🛒 طلب جديد\n\n{data}"
        
        payload = {
            "chat_id": TELEGRAM_GROUP_ID,
            "text": message_text,
            "parse_mode": "Markdown"
        }
        
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            logger.info("✅ تم إرسال الرسالة إلى التليجرام")
            return jsonify({"status": "success"})
        else:
            logger.error(f"❌ خطأ من التليجرام: {response.text}")
            return jsonify({"error": response.text}), 500
            
    except Exception as e:
        logger.error(f"❌ خطأ في webhook: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    logger.info("🚀 بدء تشغيل التطبيق...")
    logger.info(f"🔧 BOT_TOKEN: {'✅ مضبوط' if BOT_TOKEN else '❌ مفقود'}")
    logger.info(f"🔧 TELEGRAM_GROUP_ID: {'✅ مضبوط' if TELEGRAM_GROUP_ID else '❌ مفقود'}")
    logger.info(f"🔧 PORT: {PORT}")
    
    app.run(host='0.0.0.0', port=PORT, debug=False)
