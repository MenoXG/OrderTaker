import http.server
import socketserver
import json
import os
import logging
from urllib.parse import urlparse
import requests

# إعداد logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# متغيرات البيئة
BOT_TOKEN = os.environ.get('BOT_TOKEN')
TELEGRAM_GROUP_ID = os.environ.get('TELEGRAM_GROUP_ID')
PORT = int(os.environ.get('PORT', 8000))

class TelegramHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        try:
            if self.path == '/health' or self.path == '/':
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = json.dumps({
                    "status": "healthy", 
                    "service": "SendPulse Bot",
                    "bot_configured": bool(BOT_TOKEN and TELEGRAM_GROUP_ID)
                })
                self.wfile.write(response.encode())
                logger.info("✅ Health check passed")
            else:
                self.send_response(404)
                self.end_headers()
        except Exception as e:
            logger.error(f"GET error: {e}")

    def do_POST(self):
        try:
            if self.path == '/webhook/sendpulse':
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length)
                
                logger.info("📨 Received SendPulse webhook")
                
                # معالجة البيانات
                data = json.loads(post_data.decode()) if post_data else {}
                
                if BOT_TOKEN and TELEGRAM_GROUP_ID:
                    # إرسال إلى التليجرام
                    message = self.format_message(data)
                    self.send_to_telegram(message)
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    response = json.dumps({"status": "success"})
                    self.wfile.write(response.encode())
                    logger.info("✅ Message sent to Telegram")
                else:
                    self.send_response(500)
                    self.end_headers()
            else:
                self.send_response(404)
                self.end_headers()
                
        except Exception as e:
            logger.error(f"POST error: {e}")
            self.send_response(500)
            self.end_headers()

    def format_message(self, data):
        """تنسيق رسالة SendPulse"""
        full_name = data.get('full_name', 'غير معروف')
        product = data.get('Agent', 'غير معروف')
        amount = data.get('much2', 'غير معروف')
        
        return f"""🛒 **طلب جديد من SendPulse**

👤 العميل: {full_name}
📦 المنتج: {product}
💵 المبلغ: {amount} جنيه

⚡ تم الاستلام تلقائياً"""

    def send_to_telegram(self, message):
        """إرسال رسالة إلى التليجرام"""
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_GROUP_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        requests.post(url, json=payload, timeout=10)

    def log_message(self, format, *args):
        logger.info(f"🌐 {self.address_string()} - {format % args}")

def main():
    logger.info("🚀 Starting SendPulse Server")
    logger.info(f"📍 Port: {PORT}")
    
    with socketserver.TCPServer(("", PORT), TelegramHandler) as httpd:
        logger.info(f"✅ Server running on port {PORT}")
        httpd.serve_forever()

if __name__ == '__main__':
    main()
