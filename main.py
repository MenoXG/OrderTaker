import os
import requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")
SENDPULSE_TOKEN = os.getenv("SENDPULSE_TOKEN")

if not BOT_TOKEN or not GROUP_ID or not SENDPULSE_TOKEN:
    print("❌ Error: Missing environment variables (BOT_TOKEN, GROUP_ID, SENDPULSE_TOKEN)")
    raise SystemExit(1)


@app.route("/", methods=["GET"])
def home():
    return "Bot is running!", 200


@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.json
        if not data:
            return {"error": "no data"}, 400

        full_name = data.get("full_name", "")
        username = data.get("username", "")
        agent = data.get("Agent", "")
        price_in = data.get("PriceIN", "")
        much2 = data.get("much2", "")
        paid_by = data.get("PaidBy", "")
        instacontrol = data.get("InstaControl", "")
        short_url = data.get("ShortUrl", "")
        much = data.get("much", "")
        platform = data.get("Platform", "")
        redid = data.get("redid", "")
        note = data.get("Note", "")
        contact_id = data.get("contact_id", "")

        message = (
            f"👤 Name: {full_name}\n"
            f"🔗 Username: @{username}\n"
            f"🧑‍💻 Agent: {agent}\n"
            f"💰 Price: {price_in}\n"
            f"📦 Amount: {much2}\n"
            f"💳 PaidBy: {paid_by}\n"
            f"👤 InstaControl: {instacontrol}\n"
            f"🔗 ShortUrl: {short_url}\n"
            f"💵 much: {much}\n"
            f"🏦 Platform: {platform}\n"
            f"🆔 redid: {redid}\n"
            f"📝 Note: {note}\n"
            f"📞 Contact ID: {contact_id}"
        )

        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        resp = requests.post(url, json={"chat_id": GROUP_ID, "text": message})
        print("✅ Telegram response:", resp.text)

        return {"status": "ok"}, 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}, 500


@app.route("/health", methods=["GET"])
def health():
    return {"status": "healthy"}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
