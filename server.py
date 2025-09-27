# server.py - الإصدار النهائي المعدل
import http.server
import socketserver
import json
import os
import logging
import requests
import time
from threading import Thread

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
TELEGRAM_GROUP_ID = os.environ.get('TELEGRAM_GROUP_ID')
PORT = int(os.environ.get('PORT', 8000))

class HealthCheckHandler(http.server.SimpleHTTPRequestHandler):
    """معالج بسيط للـ Health Checks فقط"""
    
    def do_GET(self):
        # الرد الفوري على أي طلب GET
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')
        
    def log_message(self, format, *args):
        logger.info(f"Health check: {self.path}")

def start_health_server():
    """بدء خادم منفصل للـ Health Checks"""
    try:
        health_port = 8080  # المنفذ الذي يتوقعه Railway
        with socketserver.TCPServer(("", health_port), HealthCheckHandler) as httpd:
            logger.info(f"🏥 Health check server running on port {health_port}")
            httpd.serve_forever()
    except Exception as e:
        logger.error(f"Health server error: {e}")

def main():
    """الخادم الرئيسي للتطبيق"""
    logger.info("🚀 Starting main application server")
    
    # بدء خادم Health Checks في thread منفصل
    health_thread = Thread(target=start_health_server, daemon=True)
    health_thread.start()
    
    # هنا يمكنك وضع منطق التطبيق الرئيسي
    logger.info("✅ Application is ready")
    
    # البقاء نشطاً
    try:
        while True:
            time.sleep(60)
            logger.info("💓 Application heartbeat")
    except KeyboardInterrupt:
        logger.info("🛑 Application stopped")

if __name__ == '__main__':
    main()
