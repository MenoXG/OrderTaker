# healthcheck.py
from flask import Flask
app = Flask(__name__)

@app.route('/')
def health():
    return "healthy"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
