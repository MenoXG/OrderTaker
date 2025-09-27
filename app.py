from flask import Flask, request, jsonify
import os
import requests
import time

app = Flask(__name__)

# متغيرات البيئة
BOT_TOKEN = os.environ.get('BOT_TOKEN')
TELEGRAM_GROUP_ID = os.environ.get('TELEGRAM_GROUP_ID')

@app.route('/')
def home():
    return jsonify({
        "status": "running", 
        "service": "SendPulse Bot",
        "timestamp": time.time()
    })

@app.route('/health')
def health():
    return "healthy"

@app.route('/test')
def test():
    return "✅ Server is working!"

@app.route('/webhook/sendpulse', methods=['POST'])
def sendpulse_webhook():
    try:
        # الحصول على البيانات من SendPulse
        data = request.get_json()
        print(f"📨 Received webhook data: {data}")
        
        if not BOT_TOKEN or not TELEGRAM_GROUP_ID:
            return jsonify({"error": "Bot not configured"}), 500
        
        # تنسيق الرسالة
        message = format_sendpulse_message(data)
        
        # إرسال إلى التليجرام
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_GROUP_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            print("✅ Message sent to Telegram successfully!")
            return jsonify({"status": "success"})
        else:
            print(f"❌ Telegram error: {response.text}")
            return jsonify({"error": "Failed to send message"}), 500
            
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return jsonify({"error": str(e)}), 500

def format_sendpulse_message(data):
    """تنسيق رسالة SendPulse"""
    if isinstance(data, dict):
        full_name = data.get('full_name', 'غير معروف')
        username = data.get('username', 'غير معروف')
        agent = data.get('Agent', 'غير معروف')
        price = data.get('PriceIN', 'غير معروف')
        amount_egp = data.get('much2', 'غير معروف')
        paid_by = data.get('PaidBy', 'غير معروف')
        
        return f"""🛒 **طلب جديد من SendPulse**

👤 **العميل:** {full_name}
📱 **تليجرام:** @{username}  
📦 **المنتج:** {agent}
💰 **السعر:** {price}
💵 **المبلغ:** {amount_egp} جنيه {paid_by}

⏰ **الوقت:** {time.strftime('%Y-%m-%d %H:%M:%S')}"""
    else:
        return f"📨 **طلب جديد**\n\n{str(data)}"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    print(f"🚀 Starting Flask app on port {port}")
    print(f"🔧 BOT_TOKEN: {'✅' if BOT_TOKEN else '❌'}")
    print(f"🔧 TELEGRAM_GROUP_ID: {'✅' if TELEGRAM_GROUP_ID else '❌'}")
    app.run(host='0.0.0.0', port=port, debug=False)
