from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SENDPULSE_ID = os.getenv("SENDPULSE_API_ID")
SENDPULSE_SECRET = os.getenv("SENDPULSE_API_SECRET")

@app.route(f"/telegram/{TELEGRAM_TOKEN}", methods=["POST"])
def telegram_webhook():
    data = request.get_json(force=True)

    # ✅ Debug log - اطبع كل رسالة توصل
    print("📩 Update from Telegram:", data, flush=True)

    if "callback_query" in data:
        query = data["callback_query"]
        callback_id = query["id"]
        callback_data = query.get("data", "")
        message = query["message"]
        chat_id = message["chat"]["id"]
        message_id = message["message_id"]

        # رجع رد سريع عشان الزر يبان إنه اشتغل
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery",
                      json={"callback_query_id": callback_id})

        # ✅ Debug log - اطبع البيانات المهمة
        print(f"➡️ Callback pressed: {callback_data}", flush=True)

    return jsonify(ok=True)

if __name__ == "__main__":
    app.run(port=5000)
