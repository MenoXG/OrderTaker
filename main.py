import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# جلب المتغيرات من البيئة
SENDPULSE_API_ID = os.getenv("SENDPULSE_API_ID")
SENDPULSE_API_SECRET = os.getenv("SENDPULSE_API_SECRET")
GROUP_ID = os.getenv("GROUP_ID")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# دالة للحصول على Access Token من SendPulse
def get_sendpulse_token():
    if not SENDPULSE_API_ID or not SENDPULSE_API_SECRET:
        raise ValueError("❌ SENDPULSE_API_ID or SENDPULSE_API_SECRET not set in Railway variables")

    url = "https://api.sendpulse.com/oauth/access_token"
    data = {
        "grant_type": "client_credentials",
        "client_id": SENDPULSE_API_ID,
        "client_secret": SENDPULSE_API_SECRET
    }
    resp = requests.post(url, data=data)
    resp.raise_for_status()
    return resp.json()["access_token"]

# 🔹 Route اختبار للتأكد أن السيرفر شغال
@app.route("/")
def index():
    return "✅ Flask is running on Railway!", 200

# 🔹 استقبال رسائل تليجرام
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.json
        print("📩 Received:", data)

        # لو الرسالة من الجروب
        if "message" in data:
            chat_id = data["message"]["chat"]["id"]
            message_id = data["message"]["message_id"]

            # استقبال صورة من المسؤول
            if "photo" in data["message"]:
                file_id = data["message"]["photo"][-1]["file_id"]

                # تحميل رابط الصورة من تليجرام
                file_info = requests.get(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}"
                ).json()

                file_path = file_info["result"]["file_path"]
                file_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"

                # contact_id لازم يوصلك من SendPulse مع الرسالة
                contact_id = data["message"].get("contact_id")
                if not contact_id:
                    print("⚠️ contact_id مش موجود")
                    return jsonify({"status": "no_contact_id"}), 200

                # إرسال رابط الصورة للعميل عبر SendPulse
                token = get_sendpulse_token()
                headers = {"Authorization": f"Bearer {token}"}
                payload = {
                    "contact_id": contact_id,
                    "message": {
                        "type": "text",
                        "text": f"📸 تم تنفيذ طلبك بنجاح \n{file_url}"
                    }
                }
                resp = requests.post("https://api.sendpulse.com/telegram/contacts/sendText",
                                     json=payload, headers=headers)
                print("📤 SendPulse response:", resp.text)

                # حذف الصورة من الجروب بعد الإرسال
                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteMessage",
                    json={"chat_id": chat_id, "message_id": message_id}
                )

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print("❌ Error:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
