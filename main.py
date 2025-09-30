import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SENDPULSE_API_ID = os.getenv("SENDPULSE_API_ID")
SENDPULSE_API_SECRET = os.getenv("SENDPULSE_API_SECRET")

# نخزن أحدث contact_id مستلم
last_contact_id = None


def get_sendpulse_token():
    url = "https://api.sendpulse.com/oauth/access_token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": SENDPULSE_API_ID,
        "client_secret": SENDPULSE_API_SECRET
    }
    resp = requests.post(url, data=payload)
    return resp.json()["access_token"]


def send_text_to_client(contact_id, text, token):
    url = "https://api.sendpulse.com/telegram/contacts/sendText"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"contact_id": contact_id, "text": text}
    return requests.post(url, headers=headers, json=payload).json()


def get_file_url(file_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile"
    resp = requests.get(url, params={"file_id": file_id}).json()
    file_path = resp["result"]["file_path"]
    return f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"


def delete_message(chat_id, message_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteMessage"
    payload = {"chat_id": chat_id, "message_id": message_id}
    return requests.post(url, json=payload).json()


@app.route("/webhook", methods=["POST"])
def webhook():
    global last_contact_id
    data = request.json

    if "message" in data:
        message = data["message"]
        chat_id = message["chat"]["id"]
        message_id = message["message_id"]

        # لو استلمنا رسالة JSON من SendPulse (فيها contact_id)
        if "text" in message:
            try:
                payload = eval(message["text"])  # لو واصلة كـ string JSON
                if "contact_id" in payload:
                    last_contact_id = payload["contact_id"]
            except Exception:
                pass

        # لو استلمنا صورة بعد كده
        if "photo" in message and last_contact_id:
            file_id = message["photo"][-1]["file_id"]
            file_url = get_file_url(file_id)

            token = get_sendpulse_token()
            send_text_to_client(last_contact_id, f"📷 الصورة المرفقة:\n{file_url}", token)

            # امسح رسالة الصورة من الجروب
            delete_message(chat_id, message_id)

    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
