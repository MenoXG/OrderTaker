from flask import Flask, request
import requests
import os

app = Flask(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TARGET_CHAT_ID = os.getenv("TARGET_CHAT_ID")  # الجروب أو القناة اللي عايز تنقل لها

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()

    if "message" in data:
        message = data["message"]

        chat_id = message["chat"]["id"]
        message_id = message["message_id"]

        # نعمل sendCopy (زي forward بس من غير ما يظهر إنها forwarded)
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/copyMessage"
        payload = {
            "chat_id": TARGET_CHAT_ID,
            "from_chat_id": chat_id,
            "message_id": message_id
        }
        requests.post(url, json=payload)

    return {"ok": True}

if __name__ == '__main__':
    app.run(port=5000)
