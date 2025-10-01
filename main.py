import os
import requests
from flask import Flask, request
import logging
import time
import tempfile
import shutil
from urllib.parse import urlparse

# إعداد logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ذاكرة مؤقتة (chat_id → (contact_id, channel))
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
# 2. إرسال رسالة للعميل عبر SendPulse (للقنوات المختلفة)
# =============================
def send_to_client(contact_id, text, channel="telegram"):
    try:
        token = get_sendpulse_token()
        if not token:
            logger.error("No token available for SendPulse")
            return False
        
        if channel == "telegram":
            url = "https://api.sendpulse.com/telegram/contacts/sendText"
            payload = {"contact_id": contact_id, "text": text}
        elif channel == "messenger":
            url = "https://api.sendpulse.com/messenger/contacts/sendText"
            payload = {
                "contact_id": contact_id,
                "message_type": "RESPONSE",
                "message_tag": "ACCOUNT_UPDATE",
                "text": text
            }
        else:
            logger.error(f"Unsupported channel: {channel}")
            return False
            
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            logger.info(f"Message sent to client {contact_id} via {channel}")
            return True
        else:
            logger.error(f"Failed to send message to {contact_id} via {channel}: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending to client via {channel}: {e}")
        return False

# =============================
# 3. تحميل الصورة من Telegram وإنشاء رابط مؤقت
# =============================
def download_and_create_temp_url(telegram_file_url, telegram_token, contact_id):
    try:
        # إنشاء مجلد مؤقت في ذاكرة Railway
        temp_dir = tempfile.mkdtemp()
        file_extension = os.path.splitext(urlparse(telegram_file_url).path)[1] or '.jpg'
        file_path = os.path.join(temp_dir, f"photo_{contact_id}{file_extension}")
        
        logger.info(f"Downloading photo from: {telegram_file_url}")
        
        # تحميل الصورة من Telegram
        response = requests.get(telegram_file_url, stream=True, timeout=30)
        
        if response.status_code == 200:
            # حفظ الصورة في الملف المؤقت
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # الحصول على حجم الملف
            file_size = os.path.getsize(file_path)
            logger.info(f"Photo downloaded successfully: {file_size} bytes")
            
            if file_size == 0:
                logger.error("Downloaded file is empty")
                shutil.rmtree(temp_dir)
                return None
            
            # استخدام transfer.sh (خدمة مؤقتة مجانية)
            try:
                with open(file_path, 'rb') as f:
                    transfer_response = requests.put(
                        f'https://transfer.sh/photo_{contact_id}{file_extension}',
                        data=f,
                        headers={'Max-Days': '1'},
                        timeout=30
                    )
                
                if transfer_response.status_code == 200:
                    transfer_url = transfer_response.text.strip()
                    logger.info(f"Temporary URL created: {transfer_url}")
                    shutil.rmtree(temp_dir)
                    return transfer_url
            except Exception as e:
                logger.warning(f"transfer.sh failed: {e}")
            
            # إذا فشلت المحاولة
            logger.error("Temporary file service failed")
            shutil.rmtree(temp_dir)
            return None
            
        else:
            logger.error(f"Failed to download photo: {response.status_code}")
            shutil.rmtree(temp_dir)
            return None
            
    except Exception as e:
        logger.error(f"Error in download_and_create_temp_url: {e}")
        # تنظيف الملف المؤقت في حالة الخطأ
        if 'temp_dir' in locals() and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        return None

# =============================
# 4. إرسال صورة للعميل عبر SendPulse API (للقنوات المختلفة)
# =============================
def send_photo_to_client(contact_id, photo_url, channel="telegram"):
    try:
        token = get_sendpulse_token()
        if not token:
            logger.error("No token available for SendPulse")
            return False
        
        if channel == "telegram":
            url = "https://api.sendpulse.com/telegram/contacts/send"
            payload = {
                "contact_id": contact_id,
                "message": {
                    "type": "photo",
                    "photo": photo_url,
                    "caption": "📸 صورة من فريق الدعم الفني"
                }
            }
        elif channel == "messenger":
            url = "https://api.sendpulse.com/messenger/contacts/send"
            payload = {
                "contact_id": contact_id,
                "message": {
                    "type": "RESPONSE",
                    "tag": "CUSTOMER_FEEDBACK",
                    "content_type": "media_img",
                    "img": photo_url
                }
            }
        else:
            logger.error(f"Unsupported channel for photo: {channel}")
            return False
        
        headers = {"Authorization": f"Bearer {token}"}
        
        logger.info(f"Sending photo to contact {contact_id} via {channel}")
        logger.info(f"Photo URL: {photo_url}")
        
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        logger.info(f"SendPulse response status: {response.status_code}")
        
        if response.status_code == 200:
            logger.info(f"Photo sent successfully to client {contact_id} via {channel}")
            return True
        else:
            error_text = response.text if hasattr(response, 'text') else 'No response text'
            logger.error(f"Failed to send photo to {contact_id} via {channel}: {response.status_code} - {error_text}")
            return False
    except Exception as e:
        logger.error(f"Error sending photo to client via {channel}: {e}")
        return False

# =============================
# 5. إرسال رسالة إلى جروب تليجرام مع أزرار
# =============================
def send_to_telegram(message, contact_id, channel="telegram"):
    try:
        token = os.getenv("TELEGRAM_TOKEN")
        group_id = os.getenv("GROUP_ID")

        if not token or not group_id:
            logger.error("TELEGRAM_TOKEN or GROUP_ID not set")
            return False

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        
        # إنشاء رابط SendPulse المناسب للقناة
        if channel == "telegram":
            sendpulse_url = f"https://login.sendpulse.com/chatbots/chats?contact_id={contact_id}&channel=telegram"
        elif channel == "messenger":
            sendpulse_url = f"https://login.sendpulse.com/chatbots/chats?contact_id={contact_id}&channel=messenger"
        else:
            sendpulse_url = f"https://login.sendpulse.com/chatbots/chats?contact_id={contact_id}"
        
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ تم التنفيذ", "callback_data": f"done:{contact_id}:{channel}"},
                    {"text": "❌ إلغاء", "callback_data": f"cancel:{contact_id}:{channel}"},
                ],
                [
                    {"text": "📷 إرسال صورة", "callback_data": f"sendpic:{contact_id}:{channel}"},
                    {"text": "💬 فتح المحادثة", "url": sendpulse_url}
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
            logger.info(f"Message sent to Telegram group with contact_id: {contact_id}, channel: {channel}")
            return True
        else:
            logger.error(f"Failed to send to Telegram: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending to Telegram: {e}")
        return False

# =============================
# 6. استقبال Webhook من SendPulse
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
        channel = data.get("channel", "telegram")  # القناة الافتراضية هي telegram

        if not contact_id:
            logger.error("No contact_id received in webhook")
            return {"status": "error", "message": "No contact_id"}, 400

        # إضافة معلومات القناة للرسالة
        message = f"""
📩 <b>طلب جديد من {agent}</b>
🌐 <b>القناة: {channel.upper()}</b>

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
        success = send_to_telegram(message, contact_id, channel)
        
        if success:
            return {"status": "ok"}, 200
        else:
            return {"status": "error", "message": "Failed to send to Telegram"}, 500
            
    except Exception as e:
        logger.error(f"Error in webhook: {e}")
        return {"status": "error", "message": str(e)}, 500

# =============================
# 7. استقبال ضغط الأزرار + الصور من التليجرام
# =============================
@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    try:
        token = os.getenv("TELEGRAM_TOKEN")
        if not token:
            logger.error("TELEGRAM_TOKEN not set")
            return {"status": "error"}, 500

        data = request.get_json()
        
        # إذا لم تكن هناك بيانات، نعود بنجاح (لأن التليجرام قد يرسل طلبات اختبار)
        if not data:
            logger.info("Empty Telegram webhook received")
            return {"status": "ok"}, 200

        logger.info(f"Received Telegram update")

        # التعامل مع الأزرار
        if "callback_query" in data:
            callback = data["callback_query"]
            query_id = callback["id"]
            chat_id = callback["message"]["chat"]["id"]
            message_id = callback["message"]["message_id"]
            callback_data = callback["data"]

            logger.info(f"Callback received: {callback_data} from chat {chat_id}")

            # الرد على callback query لإزالة "Loading" من الزر
            try:
                requests.post(
                    f"https://api.telegram.org/bot{token}/answerCallbackQuery",
                    json={"callback_query_id": query_id},
                    timeout=10
                )
            except Exception as e:
                logger.error(f"Error answering callback query: {e}")

            # معالجة الإجراءات المختلفة مع استخراج channel
            new_text = ""
            if callback_data.startswith("done:"):
                parts = callback_data.split(":")
                contact_id = parts[1]
                channel = parts[2] if len(parts) > 2 else "telegram"
                send_to_client(contact_id, "✅ تم تنفيذ طلبك بنجاح", channel)
                new_text = f"✅ تم تنفيذ الطلب.\nContact ID: {contact_id}\nالقناة: {channel}"
                
            elif callback_data.startswith("cancel:"):
                parts = callback_data.split(":")
                contact_id = parts[1]
                channel = parts[2] if len(parts) > 2 else "telegram"
                send_to_client(contact_id, "❌ تم إلغاء طلبك.", channel)
                new_text = f"❌ تم إلغاء الطلب.\nContact ID: {contact_id}\nالقناة: {channel}"
                
            elif callback_data.startswith("sendpic:"):
                parts = callback_data.split(":")
                contact_id = parts[1]
                channel = parts[2] if len(parts) > 2 else "telegram"
                pending_photos[str(chat_id)] = (contact_id, channel)
                new_text = f"📷 من فضلك ارفع صورة في الجروب وسأقوم بإرسالها للعميل.\nContact ID: {contact_id}\nالقناة: {channel}"
                
            else:
                new_text = "ℹ️ عملية غير معروفة."

            # تعديل الرسالة الأصلية في الجروب
            if new_text:
                try:
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
                except Exception as e:
                    logger.error(f"Error editing message: {e}")

        # التعامل مع الصور
        elif "message" in data and "photo" in data["message"]:
            message_data = data["message"]
            chat_id = message_data["chat"]["id"]
            message_id = message_data["message_id"]

            logger.info(f"Photo received in chat {chat_id}")

            if str(chat_id) in pending_photos:
                contact_id, channel = pending_photos.pop(str(chat_id))
                # نأخذ أعلى دقة للصورة (آخر عنصر في المصفوفة)
                photo = message_data["photo"][-1]
                file_id = photo["file_id"]

                logger.info(f"Processing photo for contact {contact_id} via {channel}")

                # الحصول على معلومات الملف
                try:
                    file_info_url = f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}"
                    file_info_response = requests.get(file_info_url, timeout=30)
                    
                    if file_info_response.status_code == 200:
                        file_info = file_info_response.json()
                        if file_info.get("ok"):
                            file_path = file_info["result"]["file_path"]
                            file_url = f"https://api.telegram.org/file/bot{token}/{file_path}"

                            logger.info(f"Telegram file URL: {file_url}")
                            
                            # 1. تحميل الصورة وإنشاء رابط مؤقت
                            temp_photo_url = download_and_create_temp_url(file_url, token, contact_id)
                            
                            if temp_photo_url:
                                # 2. إرسال الصورة باستخدام الرابط المؤقت والقناة المناسبة
                                success = send_photo_to_client(contact_id, temp_photo_url, channel)
                                
                                if success:
                                    # 3. إرسال رسالة تأكيد في الجروب
                                    try:
                                        requests.post(
                                            f"https://api.telegram.org/bot{token}/sendMessage",
                                            json={
                                                "chat_id": chat_id,
                                                "text": f"✅ تم إرسال الصورة للعميل (Contact ID: {contact_id}, القناة: {channel})",
                                                "reply_to_message_id": message_id
                                            },
                                            timeout=30
                                        )
                                    except Exception as e:
                                        logger.error(f"Error sending confirmation: {e}")
                                    logger.info(f"Photo sent successfully to client {contact_id} via {channel}")
                                else:
                                    logger.error(f"Failed to send photo to client {contact_id} via {channel}")
                                    # إذا فشل إرسال الصورة، نرسل الرابط المؤقت كبديل
                                    send_to_client(contact_id, f"📸 صورة من الدعم الفني: {temp_photo_url}", channel)
                            else:
                                logger.error("Failed to create temporary photo URL")
                                # إذا فشل إنشاء الرابط المؤقت، نرسل الرابط الأصلي
                                send_to_client(contact_id, f"📸 صورة من الدعم الفني: {file_url}", channel)
                except Exception as e:
                    logger.error(f"Error processing file info: {e}")
                    # في حالة الخطأ، نرسل رسالة للعميل أن هناك مشكلة
                    send_to_client(contact_id, "📸 نعتذر، حدثت مشكلة في إرسال الصورة. يرجى المحاولة لاحقاً.", channel)

        return {"status": "ok"}, 200
        
    except Exception as e:
        logger.error(f"Error in Telegram webhook: {e}")
        return {"status": "error", "message": str(e)}, 500

# =============================
# 8. صفحات التحقق
# =============================
@app.route("/")
def home():
    return {
        "status": "running",
        "service": "Multi-Channel Telegram Bot Webhook",
        "timestamp": time.time()
    }

@app.route("/health")
def health():
    return {"status": "healthy", "timestamp": time.time()}, 200

# =============================
# 9. إعداد وإدارة Webhook للتليجرام
# =============================
@app.route("/set_webhook")
def set_webhook():
    try:
        token = os.getenv("TELEGRAM_TOKEN")
        webhook_url = os.getenv("RAILWAY_STATIC_URL")
        
        if not webhook_url:
            return {"error": "RAILWAY_STATIC_URL not set"}, 400
        
        url = f"https://api.telegram.org/bot{token}/setWebhook?url={webhook_url}/telegram"
        response = requests.get(url, timeout=30)
        result = response.json()
    logger.info(f"Webhook set: {result}")
        return result
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        return {"error": str(e)}, 500

@app.route("/webhook_info")
def webhook_info():
    try:
        token = os.getenv("TELEGRAM_TOKEN")
        if not token:
            return {"error": "TELEGRAM_TOKEN not set"}, 400
            
        url = f"https://api.telegram.org/bot{token}/getWebhookInfo"
        response = requests.get(url, timeout=30)
        return response.json()
    except Exception as e:
        return {"error": str(e)}, 500

# تشغيل التطبيق
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info(f"Starting server on port {port}")
    
    # التحقق من المتغيرات البيئية الأساسية
    required_vars = ["TELEGRAM_TOKEN", "GROUP_ID", "SENDPULSE_API_ID", "SENDPULSE_API_SECRET"]
    for var in required_vars:
        if not os.getenv(var):
            logger.warning(f"Environment variable {var} is not set")
    
    app.run(host="0.0.0.0", port=port, debug=False)
