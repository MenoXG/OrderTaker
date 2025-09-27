# app.py - احفظ هذا الكود فقط
from flask import Flask
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ OK"

@app.route('/health')
def health():
    return "healthy"

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
