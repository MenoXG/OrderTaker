# healthcheck.py - خادم منفصل للـ Health Checks
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PORT = int(os.environ.get('PORT', 8080))

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"status":"healthy"}')
    
    def log_message(self, format, *args):
        logger.info(f"Health check: {self.path}")

if __name__ == '__main__':
    logger.info(f"Starting health check server on port {PORT}")
    server = HTTPServer(('', PORT), HealthHandler)
    server.serve_forever()
