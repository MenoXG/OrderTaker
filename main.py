import os
import requests
from flask import Flask, request

app = Flask(__name__)

# Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")

# SendPulse credentials
SENDPULSE_CLIENT_ID = os.getenv("SENDPULSE_CLIENT_ID")
SENDPULSE_CLIENT_SECRET = os.getenv("SENDPULSE_CLIENT_SECRET")

if not BOT_TOKEN or not GROUP_ID or not SENDPULSE_CLIENT_ID or not SENDPULSE_CLIENT_SECRET:
    print("❌ Error: Missing environment variables")
    raise SystemExit(1)


def get_sendpulse_token():
    """
    Get access token from SendPulse using client_id and client_secret
    """
    url = "https://api.sendpulse.com/oauth/access_token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": SENDPULSE_CLIENT_ID,
        "client_secret": SENDPULSE_CLIENT_SECRET,
    }
    try:
        resp = requests.post(url, data=payload)
        resp.raise_for_status()
        token = resp.json().get("access_token")
        return token
    except Exception as e:
        print("❌ Error getting SendPulse token:", e)
        return None


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

        # Send to Telegram group
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
