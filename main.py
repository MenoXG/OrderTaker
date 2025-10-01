import os
import requests
from flask import Flask, request, jsonify
import logging
import time

# إعداد logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ذاكرة مؤقتة (chat_id → contact_id)
pending_photos = {}

# =============================
# 1. دالة للحصول على Access Token من SendPulse
# =============================
def get_sendpulse_token():
    try:
        url = "https://api.sendpulse.com/oauth/access_token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": os.getenv("SENDPULSE_API_ID"),
            "client_secret": os.getenv("SENDPULSE_API_SECRET")
        }
        response = requests.post(url, data=payload, timeout=30)
        data = response.json()
        token = data.get("access_token")
        if not token:
            logger.error("Failed to get SendPulse token")
        return token
    except Exception as e:
        logger.error(f"Error getting SendPulse token: {e}")
        return None

# =============================
# 2. إرسال رسالة للعميل عبر SendPulse
# =============================
def send_to_client(contact_id, text):
    try:
        token = get_sendpulse_token()
        if not token:
            logger.error("No token available for SendPulse")
            return False
            
        url = "https://api.sendpulse.com/telegram/contacts/sendText"
        payload = {"contact_id": contact_id, "text": text}
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            logger.info(f"Message sent to client {contact_id}")
            return True
        else:
            logger.error(f"Failed to send message to {contact_id}: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending to client: {e}")
        return False

# =============================
# 3. إرسال رسالة إلى جروب تليجرام مع أزرار
# =============================
def send_to_telegram(message, contact_id):
    try:
        token = os.getenv("TELEGRAM_TOKEN")
        group_id = os.getenv("GROUP_ID")

        if not token or not group_id:
            logger.error("TELEGRAM_TOKEN or GROUP_ID not set")
            return False

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ تم التنفيذ", "callback_data": f"done:{contact_id}"},
                    {"text": "❌ إلغاء", "callback_data": f"cancel:{contact_id}"},
                ],
                [
                    {"text": "📷 إرسال صورة", "callback_data": f"sendpic:{contact_id}"}
                ]
            ]
        }
        payload = {
            "chat_id": group_id,
            "text": message,
            "parse_mode": "HTML",
            "reply_markup": keyboard
        }
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            logger.info(f"Message sent to Telegram group with contact_id: {contact_id}")
            return True
        else:
            logger.error(f"Failed to send to Telegram: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending to Telegram: {e}")
        return False

# =============================
# 4. استقبال Webhook من SendPulse
# =============================
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        logger.info(f"Received webhook data: {data}")

        if not data:
            return {"status": "error", "message": "No data received"}, 400

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

        if not contact_id:
            logger.error("No contact_id received in webhook")
            return {"status": "error", "message": "No contact_id"}, 400

        message = f"""
📩 <b>طلب جديد من {agent}</b>

👤 الاسم: {full_name}
🔗 يوزر العميل: @{username}
🆔 رقم ID: {redid}
💳 المنصة: {platform}
💰 المبلغ: {much}
💵 مايعادلها: {price_in}
📦 الكمية: {much2}
💲 طريقة الدفع: {paid_by}
👤 محول من: {instacontrol}
📝 ملاحظات: {note}
🔗 رابط الدفع: {short_url}
📞 Contact ID: {contact_id}
"""
        success = send_to_telegram(message, contact_id)
        
        if success:
            return {"status": "ok"}, 200
        else:
            return {"status": "error", "message": "Failed to send to Telegram"}, 500
            
    except Exception as e:
        logger.error(f"Error in webhook: {e}")
        return {"status": "error", "message": str(e)}, 500

# =============================
# 5. استقبال ضغط الأزرار + الصور من التليجرام
# =============================
@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    try:
        token = os.getenv("TELEGRAM_TOKEN")
        if not token:
            logger.error("TELEGRAM_TOKEN not set")
            return {"status": "error"}, 500

        data = request.get_json()
        logger.info(f"Received Telegram update: {data}")

        if not data:
            return {"status": "ok"}, 200

        # التعامل مع الأزرار
        if "callback_query" in data:
            callback = data["callback_query"]
            query_id = callback["id"]
            chat_id = callback["message"]["chat"]["id"]
            message_id = callback["message"]["message_id"]
            callback_data = callback["data"]

            logger.info(f"Callback received: {callback_data} from chat {chat_id}")

            # الرد على callback query لإزالة "Loading" من الزر
            requests.post(
                f"https://api.telegram.org/bot{token}/answerCallbackQuery",
                json={"callback_query_id": query_id},
                timeout=30
            )

            # معالجة الإجراءات المختلفة
            if callback_data.startswith("done:"):
                contact_id = callback_data.split(":")[1]
                send_to_client(contact_id, "✅ تم تنفيذ طلبك بنجاح")
                new_text = f"✅ تم تنفيذ الطلب.\nContact ID: {contact_id}"
                
            elif callback_data.startswith("cancel:"):
                contact_id = callback_data.split(":")[1]
                send_to_client(contact_id, "❌ تم إلغاء طلبك.")
                new_text = f"❌ تم إلغاء الطلب.\nContact ID: {contact_id}"
                
            elif callback_data.startswith("sendpic:"):
                contact_id = callback_data.split(":")[1]
                pending_photos[str(chat_id)] = contact_id  # تأكد من أنه string
                new_text = f"📷 من فضلك ارفع صورة في الجروب وسأقوم بإرسالها للعميل.\nContact ID: {contact_id}"
                
            else:
                new_text = "ℹ️ عملية غير معروفة."

            # تعديل الرسالة الأصلية في الجروب
            edit_url = f"https://api.telegram.org/bot{token}/editMessageText"
            edit_payload = {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": new_text,
                "parse_mode": "HTML"
            }
            edit_response = requests.post(edit_url, json=edit_payload, timeout=30)
            
            if edit_response.status_code != 200:
                logger.error(f"Failed to edit message: {edit_response.text}")

        # التعامل مع الصور
        elif "message" in data and "photo" in data["message"]:
            message_data = data["message"]
            chat_id = message_data["chat"]["id"]
            message_id = message_data["message_id"]

            logger.info(f"Photo received in chat {chat_id}")

            if str(chat_id) in pending_photos:  # تأكد من المقارنة كـ string
                contact_id = pending_photos.pop(str(chat_id))
                # نأخذ أعلى دقة للصورة (آخر عنصر في المصفوفة)
                photo = message_data["photo"][-1]
                file_id = photo["file_id"]

                logger.info(f"Processing photo for contact {contact_id}")

                # الحصول على معلومات الملف
                file_info_url = f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}"
                file_info_response = requests.get(file_info_url, timeout=30)
                
                if file_info_response.status_code == 200:
                    file_info = file_info_response.json()
                    if file_info.get("ok"):
                        file_path = file_info["result"]["file_path"]
                        file_url = f"https://api.telegram.org/file/bot{token}/{file_path}"

                        # إرسال الصورة للعميل
                        success = send_to_client(contact_id, f"📷 تم استلام صورة من الدعم الفني:\n{file_url}")
                        
                        if success:
                            # إرسال رسالة تأكيد في الجروب
                            requests.post(
                                f"https://api.telegram.org/bot{token}/sendMessage",
                                json={
                                    "chat_id": chat_id,
                                    "text": f"✅ تم إرسال الصورة للعميل (Contact ID: {contact_id})",
                                    "reply_to_message_id": message_id
                                },
                                timeout=30
                            )
                            logger.info(f"Photo sent to client {contact_id}")
                        else:
                            logger.error(f"Failed to send photo to client {contact_id}")
                    else:
                        logger.error("File info not OK in response")
                else:
                    logger.error("Failed to get file info from Telegram")

        return {"status": "ok"}, 200
        
    except Exception as e:
        logger.error(f"Error in Telegram webhook: {e}")
        return {"status": "error", "message": str(e)}, 500

# =============================
# 6. صفحة رئيسية للتحقق من أن الخادم يعمل
# =============================
@app.route("/")
def home():
    return {
        "status": "running",
        "service": "Telegram Bot Webhook",
        "timestamp": time.time(),
        "endpoints": {
            "webhook": "/webhook (POST)",
            "telegram": "/telegram (POST)",
            "health": "/health (GET)",
            "set_webhook": "/set_webhook (GET)"
        }
    }

@app.route("/health")
def health():
    return {"status": "healthy", "timestamp": time.time()}, 200

# =============================
# 7. إعداد Webhook للتليجرام
# =============================
@app.route("/set_webhook")
def set_webhook():
    try:
        token = os.getenv("TELEGRAM_TOKEN")
        webhook_url = os.getenv("RAILWAY_STATIC_URL")
        
        if not webhook_url:
            webhook_url = f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN')}"
            
        if not webhook_url:
            return {"error": "RAILWAY_STATIC_URL or RAILWAY_PUBLIC_DOMAIN not set"}, 400
        
        url = f"https://api.telegram.org/bot{token}/setWebhook?url={webhook_url}/telegram"
        response = requests.get(url, timeout=30)
        result = response.json()
        logger.info(f"Webhook set: {result}")
        return result
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        return {"error": str(e)}, 500

# تشغيل التطبيق
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info(f"Starting server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
