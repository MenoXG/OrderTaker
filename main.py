import os
import requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")  # ID الجروب
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# نخزن آخر رسالة أرسلها البوت
last_bot_message_id = None


@app.route("/webhook", methods=["POST"])
def webhook():
    global last_bot_message_id

    data = request.json
    print("📩 Received data from SendPulse:", data)

    if not data or "message" not in data:
        print("⚠️ No 'message' found in payload")
        return {"status": "no message"}, 200

    msg_text = data["message"]

    # 1️⃣ إرسال الرسالة الجديدة مع الأزرار
    send_resp = requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": CHAT_ID,
        "text": f"📩 طلب جديد:\n{msg_text}",
        "reply_markup": {
            "inline_keyboard": [[
                {"text": "✅ تم التحويل", "callback_data": "confirm"},
                {"text": "❌ إلغاء الطلب", "callback_data": "cancel"}
            ]]
        }
    })

    print("📤 Telegram sendMessage response:", send_resp.text)
    resp_json = send_resp.json()

    if not resp_json.get("ok"):
        print("❌ Failed to send message:", resp_json)
        return {"status": "telegram error"}, 500

    # نخزن message_id للرسالة الجديدة
    new_msg_id = resp_json["result"]["message_id"]

    # 2️⃣ لو فيه رسالة قديمة مخزنة → نحذفها
    if last_bot_message_id:
        del_resp = requests.post(f"{TELEGRAM_API}/deleteMessage", json={
            "chat_id": CHAT_ID,
            "message_id": last_bot_message_id
        })
        print("🗑️ Delete old bot message response:", del_resp.text)

    # تحديث التخزين بالرسالة الجديدة
    last_bot_message_id = new_msg_id

    return {"status": "ok"}, 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
