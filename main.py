from flask import Flask, request, jsonify
import os
import logging
import requests
import time

# إعداد logging سريع
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

# تهيئة سريعة عند استيراد الملف
logger.info("🚀 تهيئة التطبيق...")

@app.route('/')
def home():
    """الصفحة الرئيسية - استجابة فورية"""
    return jsonify({
        "status": "running", 
        "service": "SendPulse Bot",
        "timestamp": time.time()
    })

@app.route('/health')
def health():
    """Health check فوري"""
    return jsonify({"status": "healthy", "timestamp": time.time()})

@app.route('/ready')
def ready():
    """Endpoint للتحقق من جاهزية التطبيق"""
    return jsonify({"status": "ready"})

@app.route('/webhook/sendpulse', methods=['GET', 'POST'])
def sendpulse_webhook():
    """Webhook لاستقبال إشعارات SendPulse"""
    try:
        if request.method == 'GET':
            return jsonify({"message": "SendPulse webhook is ready"})
        
        logger.info("📨 تم استلام webhook من SendPulse")
        
        # معالجة البيانات بسرعة
        data = request.get_json(silent=True) or request.get_data(as_text=True)
        
        if not BOT_TOKEN or not TELEGRAM_GROUP_ID:
            return jsonify({"error": "Bot not configured"}), 500
        
        # إرسال سريع إلى التليجرام
        message_text = "🛒 طلب جديد من SendPulse\n\n" + str(data)[:500]
        
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_GROUP_ID,
            "text": message_text,
            "parse_mode": "Markdown"
        }
        
        response = requests.post(url, json=payload, timeout=5)
        
        if response.status_code == 200:
            return jsonify({"status": "success"})
        else:
            return jsonify({"error": "Telegram API error"}), 500
            
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"error": str(e)}), 500

def create_app():
    """دالة لإنشاء التطبيق (مطلوبة لـ Gunicorn)"""
    return app

if __name__ == '__main__':
    # بدء سريع بدون خيارات معقدة
    logger.info(f"Starting Flask app on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False)
