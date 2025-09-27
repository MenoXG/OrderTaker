import http.server
import socketserver
import json
import os
import logging
import requests
import threading
import time

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
            # الرد الفوري على أي طلب GET (لـ health checks)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            response = json.dumps({
                "status": "healthy", 
                "service": "SendPulse Bot",
                "timestamp": time.time(),
                "path": self.path
            })
            self.wfile.write(response.encode())
            
            logger.info(f"✅ Health check: {self.path}")
            
        except Exception as e:
            logger.error(f"GET error: {e}")

    def do_POST(self):
        try:
            if self.path == '/webhook/sendpulse':
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length)
                
                logger.info("📨 Received SendPulse webhook")
                
                # الرد الفوري أولاً
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "received"}).encode())
                
                # ثم معالجة البيانات في thread منفصل
                threading.Thread(target=self.process_webhook, args=(post_data,)).start()
                
            else:
                self.send_response(404)
                self.end_headers()
                
        except Exception as e:
            logger.error(f"POST error: {e}")
            self.send_response(500)
            self.end_headers()

    def process_webhook(self, post_data):
        """معالجة webhook في thread منفصل"""
        try:
            data = json.loads(post_data.decode()) if post_data else {}
            logger.info(f"📊 Processing webhook data: {data}")
            
            if BOT_TOKEN and TELEGRAM_GROUP_ID:
                message = self.format_message(data)
                self.send_to_telegram(message)
                logger.info("✅ Message sent to Telegram")
            else:
                logger.error("❌ Bot not configured")
                
        except Exception as e:
            logger.error(f"❌ Error processing webhook: {e}")

    def format_message(self, data):
        """تنسيق رسالة SendPulse"""
        full_name = data.get('full_name', 'غير معروف')
        username = data.get('username', 'غير معروف')
        agent = data.get('Agent', 'غير معروف')
        price = data.get('PriceIN', 'غير معروف')
        amount_egp = data.get('much2', 'غير معروف')
        paid_by = data.get('PaidBy', 'غير معروف')
        short_url = data.get('ShortUrl', 'غير معروف')
        amount_usd = data.get('much', 'غير معروف')
        platform = data.get('Platform', 'غير معروف')
        redid = data.get('redid', 'غير معروف')
        
        return f"""🛒 **طلب جديد من SendPulse**

👤 **العميل:** {full_name}
📱 **تليجرام:** @{username}
📦 **المنتج:** {agent}
💰 **سعر البيع:** {price}
💵 **المبلغ:** {amount_egp} جنيه {paid_by}
🔗 **الرابط:** {short_url}
💳 **الرصيد:** {amount_usd} $ {platform}
🆔 **المعرف:** {redid}

⏰ **الوقت:** {time.strftime('%Y-%m-%d %H:%M:%S')}"""

    def send_to_telegram(self, message):
        """إرسال رسالة إلى التليجرام"""
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": TELEGRAM_GROUP_ID,
                "text": message,
                "parse_mode": "Markdown"
            }
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code != 200:
                logger.error(f"❌ Telegram API error: {response.text}")
        except Exception as e:
            logger.error(f"❌ Error sending to Telegram: {e}")

    def log_message(self, format, *args):
        logger.info(f"🌐 {self.address_string()} - {format % args}")

def main():
    logger.info("🚀 Starting SendPulse Server")
    logger.info(f"📍 Port: {PORT}")
    logger.info(f"🤖 Bot: {'✅ Configured' if BOT_TOKEN else '❌ Missing'}")
    logger.info(f"👥 Group: {'✅ Configured' if TELEGRAM_GROUP_ID else '❌ Missing'}")
    
    # بدء الخادم مع إعدادات محسنة
    with socketserver.TCPServer(("", PORT), TelegramHandler) as httpd:
        httpd.timeout = 30  # زيادة timeout
        logger.info(f"✅ Server running on port {PORT}")
        
        # إرسال رسالة بدء التشغيل إلى التليجرام
        if BOT_TOKEN and TELEGRAM_GROUP_ID:
            try:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                payload = {
                    "chat_id": TELEGRAM_GROUP_ID,
                    "text": "🚀 SendPulse Bot started successfully!",
                    "parse_mode": "Markdown"
                }
                requests.post(url, json=payload, timeout=5)
                logger.info("✅ Startup message sent to Telegram")
            except:
                logger.warning("⚠️ Could not send startup message")
        
        # الاستمرار في التشغيل
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            logger.info("🛑 Server stopped by user")
        except Exception as e:
            logger.error(f"❌ Server error: {e}")

if __name__ == '__main__':
    main()
