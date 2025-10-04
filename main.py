import os
import requests
from flask import Flask, request
import logging
import time
import tempfile
import shutil
import threading

# إعداد logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ذاكرة مؤقتة (chat_id → {contact_id, channel, request_message_id})
pending_photos = {}

# Flow IDs لكل قناة
FLOW_IDS = {
    "telegram": {
        "transfer_minus": "6856d410b7a060fae70c2ea6",
        "transfer_plus": "68572471a3978f2f6609937f"
    },
    "messenger": {
        "transfer_minus": "7c354af9-9df2-4e1d-8cac-768c4ac9f472",
        "transfer_plus": "23fd4175-86c0-4882-bbe2-906f75c77a6d"
    }
}

# =============================
# 1. دالة مسح الرسائل من التليجرام
# =============================
def delete_telegram_message(chat_id, message_id):
    try:
        token = os.getenv("TELEGRAM_TOKEN")
        if not token:
            logger.error("TELEGRAM_TOKEN not set")
            return False
            
        url = f"https://api.telegram.org/bot{token}/deleteMessage"
        payload = {
            "chat_id": chat_id,
            "message_id": message_id
        }
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            logger.info(f"Message {message_id} deleted successfully from chat {chat_id}")
            return True
        else:
            logger.error(f"Failed to delete message {message_id}: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error deleting message: {e}")
        return False

# =============================
# 2. دالة مسح رسالة بعد تأخير
# =============================
def delete_message_after_delay(chat_id, message_id, delay_seconds):
    def delete():
        time.sleep(delay_seconds)
        delete_telegram_message(chat_id, message_id)
    
    thread = threading.Thread(target=delete)
    thread.daemon = True
    thread.start()

# =============================
# 3. دالة للحصول على Access Token من SendPulse
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
# 4. تشغيل Flow في SendPulse
# =============================
def run_flow(contact_id, channel, flow_type):
    try:
        token = get_sendpulse_token()
        if not token:
            logger.error("No token available for SendPulse")
            return False

        # تحديد الـ endpoint بناءً على القناة
        if channel == "telegram":
            url = "https://api.sendpulse.com/telegram/flows/run"
        elif channel == "messenger":
            url = "https://api.sendpulse.com/messenger/flows/run"
        else:
            logger.error(f"Unknown channel for flow: {channel}")
            return False

        # الحصول على الـ flow_id المناسب للقناة ونوع التحويل
        flow_id = FLOW_IDS.get(channel, {}).get(flow_type)
        if not flow_id:
            logger.error(f"No flow_id defined for channel: {channel} and flow type: {flow_type}")
            return False

        payload = {
            "contact_id": contact_id,
            "flow_id": flow_id,
            "external_data": {
                "tracking_number": "1234-0987-5678-9012"
            }
        }

        headers = {"Authorization": f"Bearer {token}"}
        
        logger.info(f"Running {flow_type} flow for contact {contact_id} on channel {channel}")
        logger.info(f"Flow ID: {flow_id}")
        
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        logger.info(f"SendPulse Flow response status: {response.status_code}")
        logger.info(f"SendPulse Flow response text: {response.text}")
        
        if response.status_code == 200:
            logger.info(f"{flow_type} flow started successfully for client {contact_id} on channel {channel}")
            return True
        else:
            logger.error(f"Failed to start {flow_type} flow for {contact_id}: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error running flow: {e}")
        return False

# =============================
# 5. إرسال رسالة للعميل عبر SendPulse (Telegram)
# =============================
def send_to_client_telegram(contact_id, text):
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
            logger.info(f"Message sent to Telegram client {contact_id}")
            return True
        else:
            logger.error(f"Failed to send message to Telegram {contact_id}: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending to Telegram client: {e}")
        return False

# =============================
# 6. إرسال رسالة للعميل عبر SendPulse (Messenger)
# =============================
def send_to_client_messenger(contact_id, text):
    try:
        token = get_sendpulse_token()
        if not token:
            logger.error("No token available for SendPulse")
            return False
            
        url = "https://api.sendpulse.com/messenger/contacts/sendText"
        payload = {
            "contact_id": contact_id,
            "message_type": "RESPONSE",
            "message_tag": "ACCOUNT_UPDATE",
            "text": text
        }
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            logger.info(f"Message sent to Messenger client {contact_id}")
            return True
        else:
            logger.error(f"Failed to send message to Messenger {contact_id}: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending to Messenger client: {e}")
        return False

# =============================
# 7. دالة موحدة لإرسال الرسائل بناءً على القناة
# =============================
def send_to_client(contact_id, text, channel):
    if channel == "telegram":
        return send_to_client_telegram(contact_id, text)
    elif channel == "messenger":
        return send_to_client_messenger(contact_id, text)
    else:
        logger.error(f"Unknown channel: {channel}")
        return False

# =============================
# 8. تحميل الصورة من Telegram وإنشاء رابط مؤقت
# =============================
def download_and_create_temp_url(telegram_file_url, telegram_token, contact_id):
    try:
        # إنشاء مجلد مؤقت في ذاكرة Railway
        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, f"photo_{contact_id}.jpg")
        
        logger.info(f"Downloading photo from: {telegram_file_url}")
        
        # تحميل الصورة من Telegram
        response = requests.get(telegram_file_url, stream=True, timeout=30)
        
        if response.status_code == 200:
            # حفظ الصورة في الملف المؤقت
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # الحصول على حجم الملف
            file_size = os.path.getsize(file_path)
            logger.info(f"Photo downloaded successfully: {file_size} bytes")
            
            # رفع الصورة إلى خدمة تخزين مؤقتة
            with open(file_path, 'rb') as f:
                upload_response = requests.post(
                    'https://tmpfiles.org/api/v1/upload',
                    files={'file': f},
                    timeout=30
                )
            
            # تنظيف الملف المؤقت
            shutil.rmtree(temp_dir)
            
            if upload_response.status_code == 200:
                upload_data = upload_response.json()
                if upload_data.get('status') == 'success':
                    # tmpfiles.org يعطينا رابط تنزيل مباشر
                    download_url = upload_data['data']['url']
                    # نحتاج لتحويل الرابط إلى صيغة مباشرة
                    direct_url = download_url.replace('tmpfiles.org/', 'tmpfiles.org/dl/')
                    logger.info(f"Temporary URL created: {direct_url}")
                    return direct_url
                else:
                    logger.error(f"Upload failed: {upload_data}")
                    return None
            else:
                logger.error(f"Upload failed with status: {upload_response.status_code}")
                return None
        else:
            logger.error(f"Failed to download photo: {response.status_code}")
            # تنظيف الملف المؤقت في حالة الخطأ
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            return None
            
    except Exception as e:
        logger.error(f"Error in download_and_create_temp_url: {e}")
        # تنظيف الملف المؤقت في حالة الخطأ
        if 'temp_dir' in locals() and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        return None

# =============================
# 9. إرسال صورة للعميل عبر SendPulse API (Telegram)
# =============================
def send_photo_to_client_telegram(contact_id, photo_url):
    try:
        token = get_sendpulse_token()
        if not token:
            logger.error("No token available for SendPulse")
            return False
            
        url = "https://api.sendpulse.com/telegram/contacts/send"
        
        payload = {
            "contact_id": contact_id,
            "message": {
                "type": "photo",
                "photo": photo_url,
                "caption": "📸 صورة من فريق الدعم الفني"
            }
        }
        
        headers = {"Authorization": f"Bearer {token}"}
        
        logger.info(f"Sending photo to Telegram contact {contact_id}")
        logger.info(f"Photo URL: {photo_url}")
        
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        logger.info(f"SendPulse Telegram response status: {response.status_code}")
        logger.info(f"SendPulse Telegram response text: {response.text}")
        
        if response.status_code == 200:
            logger.info(f"Photo sent successfully to Telegram client {contact_id}")
            return True
        else:
            logger.error(f"Failed to send photo to Telegram {contact_id}: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending photo to Telegram client: {e}")
        return False

# =============================
# 10. إرسال صورة للعميل عبر SendPulse API (Messenger)
# =============================
def send_photo_to_client_messenger(contact_id, photo_url):
    try:
        token = get_sendpulse_token()
        if not token:
            logger.error("No token available for SendPulse")
            return False
            
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
        
        headers = {"Authorization": f"Bearer {token}"}
        
        logger.info(f"Sending photo to Messenger contact {contact_id}")
        logger.info(f"Photo URL: {photo_url}")
        
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        logger.info(f"SendPulse Messenger response status: {response.status_code}")
        logger.info(f"SendPulse Messenger response text: {response.text}")
        
        if response.status_code == 200:
            logger.info(f"Photo sent successfully to Messenger client {contact_id}")
            return True
        else:
            logger.error(f"Failed to send photo to Messenger {contact_id}: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending photo to Messenger client: {e}")
        return False

# =============================
# 11. دالة موحدة لإرسال الصور بناءً على القناة
# =============================
def send_photo_to_client(contact_id, photo_url, channel):
    if channel == "telegram":
        return send_photo_to_client_telegram(contact_id, photo_url)
    elif channel == "messenger":
        return send_photo_to_client_messenger(contact_id, photo_url)
    else:
        logger.error(f"Unknown channel for photo sending: {channel}")
        return False

# =============================
# 12. إرسال رسالة إلى جروب تليجرام مع أزرار (للطلبات الجديدة)
# =============================
def send_to_telegram(message, contact_id, channel):
    try:
        token = os.getenv("TELEGRAM_TOKEN")
        group_id = os.getenv("GROUP_ID")

        if not token or not group_id:
            logger.error("TELEGRAM_TOKEN or GROUP_ID not set")
            return False

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        
        # إنشاء رابط SendPulse مع contact_id و channel
        sendpulse_url = f"https://login.sendpulse.com/chatbots/chats?contact_id={contact_id}&channel={channel}"
        
        # إضافة رمز القناة إلى الرسالة
        channel_icon = "📱" if channel == "messenger" else "✈️"
        message_with_channel = f"{channel_icon} {message}"
        
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ تم التنفيذ", "callback_data": f"done:{contact_id}:{channel}"},
                    {"text": "❌ إلغاء", "callback_data": f"cancel:{contact_id}:{channel}"},
                ],
                [
                    {"text": "📷 إرسال صورة", "callback_data": f"sendpic:{contact_id}:{channel}"},
                ],
                [
                    {"text": "🔄 تحويل ناقص", "callback_data": f"transfer_minus:{contact_id}:{channel}"},
                    {"text": "🔄 تحويل زائد", "callback_data": f"transfer_plus:{contact_id}:{channel}"}
                ],
                [
                    {"text": "💬 فتح المحادثة", "url": sendpulse_url}
                ]
            ]
        }
        payload = {
            "chat_id": group_id,
            "text": message_with_channel,
            "parse_mode": "HTML",
            "reply_markup": keyboard
        }
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            logger.info(f"Message sent to Telegram group with contact_id: {contact_id} and channel: {channel}")
            return True
        else:
            logger.error(f"Failed to send to Telegram: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending to Telegram: {e}")
        return False

# =============================
# 13. إرسال رسالة طلب صورة إضافية إلى الجروب (زر واحد فقط)
# =============================
def send_photo_request_to_telegram(message, contact_id, channel):
    try:
        token = os.getenv("TELEGRAM_TOKEN")
        group_id = os.getenv("GROUP_ID")

        if not token or not group_id:
            logger.error("TELEGRAM_TOKEN or GROUP_ID not set")
            return False

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        
        # إضافة رمز القناة إلى الرسالة
        channel_icon = "📱" if channel == "messenger" else "✈️"
        message_with_channel = f"{channel_icon} {message}"
        
        # زر واحد فقط - إرسال صورة
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "📷 إرسال صورة", "callback_data": f"sendpic:{contact_id}:{channel}"}
                ]
            ]
        }
        payload = {
            "chat_id": group_id,
            "text": message_with_channel,
            "parse_mode": "HTML",
            "reply_markup": keyboard
        }
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            logger.info(f"Photo request sent to Telegram group with contact_id: {contact_id} and channel: {channel}")
            return True
        else:
            logger.error(f"Failed to send photo request to Telegram: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending photo request to Telegram: {e}")
        return False

# =============================
# 14. استقبال Webhook من SendPulse
# =============================
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        logger.info(f"Received webhook data: {data}")

        if not data:
            return {"status": "error", "message": "No data received"}, 400

        # استخراج البيانات من الـ webhook
        full_name = data.get("full_name", "")
        username = data.get("username", "")
        agent = data.get("Agent", "")
        price_in = data.get("PriceIN", "")
        much2 = data.get("much2", "")
        paid_by = data.get("PaidBy", "")
        cash_control = data.get("CashControl", "")  # رقم/اسم المحفظة
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

        # ⚡ **الكشف عن نوع الطلب: طلب جديد أم طلب صورة إضافي**
        is_photo_request = False
        
        # إذا كان هناك بيانات أساسية للطلب (مثل Agent, PriceIN) فهذا طلب جديد
        # إذا لم تكن هناك بيانات طلب ولكن هناك contact_id و channel فقط، فهذا طلب صورة إضافي
        has_order_data = any([
            data.get("Agent"),
            data.get("PriceIN"), 
            data.get("much2"),
            data.get("PaidBy"),
            data.get("CashControl"),
            data.get("much"),
            data.get("Platform")
        ])
        
        # إذا لم تكن هناك بيانات طلب، ولكن هناك رسالة من العميل (مثل redid, note) فهذا طلب صورة إضافي
        if not has_order_data and (redid or address or kastaddress or full_name):
            is_photo_request = True
            logger.info(f"Detected photo request from client: {contact_id}")

        if is_photo_request:
            # بناء رسالة طلب الصورة الإضافية
            message_lines = ["📸 <b>طلب صورة إضافية من العميل</b>"]
            
            if full_name:
                message_lines.append(f"العميل: {full_name}")
            if username:
                message_lines.append(f"التليجرام: @{username}")
            if redid:
                message_lines.append(f"الرقم التعريفي: {redid}")
            if note:
                message_lines.append(f"الملاحظة: {note}")
                
            message = "\n".join(message_lines)
            
            # إرسال رسالة طلب الصورة الإضافية (زر واحد فقط)
            success = send_photo_request_to_telegram(message, contact_id, channel)
        else:
            # بناء رسالة الطلب الجديد
            message_lines = []
            
            # إضافة الحقول التي تحتوي على قيم فقط بنفس التنسيق المطلوب
            if full_name or username:
                line = ""
                if full_name:
                    line += f"العميل {full_name}"
                if username:
                    if line:
                        line += f" تليجرام @{username}"
                    else:
                        line += f"تليجرام @{username}"
                message_lines.append(line)
            
            if agent or price_in:
                line = ""
                if agent:
                    line += f"شفــت {agent}"
                if price_in:
                    if line:
                        line += f" سعـر البيـع {price_in}"
                    else:
                        line += f"سعـر البيـع {price_in}"
                message_lines.append(line)
            
            if much2 or paid_by:
                line = ""
                if much2:
                    line += f"المبلـغ {much2}"
                if paid_by:
                    if line:
                        line += f" جنيـه {paid_by}"
                    else:
                        line += f"جنيـه {paid_by}"
                message_lines.append(line)
            
            if cash_control:
                message_lines.append(f"رقم/اسم المحفظـة {cash_control}")
            
            if short_url:
                message_lines.append(f"الإيصـال {short_url}")
            
            if much or platform:
                line = ""
                if much:
                    line += f"الرصيــد {much}"
                if platform:
                    if line:
                        line += f" $ {platform}"
                    else:
                        line += f"$ {platform}"
                message_lines.append(line)
            
            if redid:
                message_lines.append(f"{redid}")
            
            if note:
                message_lines.append(f"{note}")
            
            # إضافة عنوان الرسالة في الأعلى
            if message_lines:
                message_lines.insert(0, "📩 <b>طلب جديد</b>")
            
            # دمج كل الأسطر في رسالة واحدة
            message = "\n".join(message_lines) if message_lines else "📩 <b>طلب جديد</b>"

            # إرسال رسالة الطلب الجديد (بجميع الأزرار)
            success = send_to_telegram(message, contact_id, channel)
        
        if success:
            return {"status": "ok"}, 200
        else:
            return {"status": "error", "message": "Failed to send to Telegram"}, 500
            
    except Exception as e:
        logger.error(f"Error in webhook: {e}")
        return {"status": "error", "message": str(e)}, 500

# =============================
# 15. استقبال ضغط الأزرار + الصور من التليجرام
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

            # تقسيم callback_data إلى أجزاء: action, contact_id, channel
            parts = callback_data.split(':')
            action = parts[0]
            contact_id = parts[1]
            channel = parts[2] if len(parts) > 2 else 'telegram'

            # معالجة الإجراءات المختلفة
            if action == "done":
                send_to_client(contact_id, "✅ تم تنفيذ طلبك بنجاح", channel)
                new_text = f"✅ تم تنفيذ الطلب بنجاح"
                
                # تعديل الرسالة الأصلية في الجروب
                edit_url = f"https://api.telegram.org/bot{token}/editMessageText"
                edit_payload = {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": new_text,
                    "parse_mode": "HTML"
                }
                edit_response = requests.post(edit_url, json=edit_payload, timeout=30)
                
                if edit_response.status_code == 200:
                    # مسح رسالة التأكيد بعد 5 ثواني
                    delete_message_after_delay(chat_id, message_id, 5)
                    logger.info(f"Success message scheduled for deletion: {message_id}")
                else:
                    logger.error(f"Failed to edit message: {edit_response.text}")
                
            elif action == "cancel":
                send_to_client(contact_id, "❌ تم إلغاء طلبك.", channel)
                new_text = f"❌ تم إلغاء الطلب"
                
                # تعديل الرسالة الأصلية في الجروب
                edit_url = f"https://api.telegram.org/bot{token}/editMessageText"
                edit_payload = {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": new_text,
                    "parse_mode": "HTML"
                }
                edit_response = requests.post(edit_url, json=edit_payload, timeout=30)
                
                if edit_response.status_code == 200:
                    # مسح رسالة التأكيد بعد 5 ثواني
                    delete_message_after_delay(chat_id, message_id, 5)
                    logger.info(f"Cancel message scheduled for deletion: {message_id}")
                else:
                    logger.error(f"Failed to edit message: {edit_response.text}")
                
            elif action == "sendpic":
                # حفظ معرف الرسالة الحالية (التي تحتوي على طلب رفع الصورة)
                pending_photos[str(chat_id)] = {
                    'contact_id': contact_id,
                    'channel': channel,
                    'request_message_id': message_id  # حفظ معرف الرسالة التي تطلب الصورة
                }
                new_text = f"📷 من فضلك ارفع صورة في الجروب وسأقوم بإرسالها للعميل"
                
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

            elif action in ["transfer_minus", "transfer_plus"]:
                # تحديد نوع الرسالة بناءً على نوع التحويل
                flow_type = action
                flow_name = "تحويل ناقص" if flow_type == "transfer_minus" else "تحويل زائد"
                
                # تشغيل Flow المناسب
                success = run_flow(contact_id, channel, flow_type)
                if success:
                    confirmation_message = f"🔄 تم {flow_name} للطلب بنجاح"
                    send_to_client(contact_id, f"🔄 تم {flow_name} لطلبك وسيتم متابعته من قبل الفريق المختص", channel)
                else:
                    confirmation_message = f"❌ فشل {flow_name} للطلب"
                
                # إرسال رسالة تأكيد منفصلة
                confirmation_response = requests.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": confirmation_message,
                        "parse_mode": "HTML"
                    },
                    timeout=30
                )
                
                if confirmation_response.status_code == 200:
                    confirmation_data = confirmation_response.json()
                    confirmation_message_id = confirmation_data['result']['message_id']
                    
                    # مسح رسالة التأكيد بعد 5 ثواني
                    delete_message_after_delay(chat_id, confirmation_message_id, 5)
                    logger.info(f"{flow_name} confirmation message scheduled for deletion: {confirmation_message_id}")
                else:
                    logger.error(f"Failed to send confirmation message: {confirmation_response.text}")

        # التعامل مع الصور
        elif "message" in data and "photo" in data["message"]:
            message_data = data["message"]
            chat_id = message_data["chat"]["id"]
            message_id = message_data["message_id"]  # معرف رسالة الصورة المرسلة

            logger.info(f"Photo received in chat {chat_id}")

            if str(chat_id) in pending_photos:
                pending_data = pending_photos.pop(str(chat_id))
                contact_id = pending_data['contact_id']
                channel = pending_data['channel']
                request_message_id = pending_data.get('request_message_id')  # معرف رسالة طلب الصورة

                # نأخذ أعلى دقة للصورة (آخر عنصر في المصفوفة)
                photo = message_data["photo"][-1]
                file_id = photo["file_id"]

                logger.info(f"Processing photo for contact {contact_id} on channel {channel}")
                logger.info(f"File ID: {file_id}")

                # الحصول على معلومات الملف
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
                            # 2. إرسال الصورة باستخدام الرابط المؤقت
                            success = send_photo_to_client(contact_id, temp_photo_url, channel)
                            
                            if success:
                                # 3. مسح الرسائل المطلوبة فور نجاح الإرسال
                                
                                # مسح رسالة طلب الصورة (إذا كانت موجودة)
                                if request_message_id:
                                    delete_telegram_message(chat_id, request_message_id)
                                
                                # مسح الصورة المرسلة في الجروب
                                delete_telegram_message(chat_id, message_id)
                                
                                # 4. إرسال رسالة تأكيد في الجروب
                                confirmation_response = requests.post(
                                    f"https://api.telegram.org/bot{token}/sendMessage",
                                    json={
                                        "chat_id": chat_id,
                                        "text": f"✅ تم إرسال الصورة للعميل بنجاح"
                                    },
                                    timeout=30
                                )
                                
                                if confirmation_response.status_code == 200:
                                    confirmation_data = confirmation_response.json()
                                    confirmation_message_id = confirmation_data['result']['message_id']
                                    
                                    # مسح رسالة التأكيد بعد 5 ثواني
                                    delete_message_after_delay(chat_id, confirmation_message_id, 5)
                                
                                logger.info(f"Photo sent successfully to client {contact_id} on channel {channel}")
                            else:
                                logger.error(f"Failed to send photo to client {contact_id} on channel {channel}")
                                # إذا فشل إرسال الصورة، نرسل الرابط كبديل
                                send_to_client(contact_id, f"📸 صورة من الدعم الفني: {temp_photo_url}", channel)
                        else:
                            logger.error("Failed to create temporary photo URL")
                            # إذا فشل إنشاء الرابط المؤقت، نرسل الرابط الأصلي
                            send_to_client(contact_id, f"📸 صورة من الدعم الفني: {file_url}", channel)

        return {"status": "ok"}, 200
        
    except Exception as e:
        logger.error(f"Error in Telegram webhook: {e}")
        return {"status": "error", "message": str(e)}, 500

# =============================
# 16. صفحات التحقق
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
# 17. إعداد Webhook للتليجرام
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

# تشغيل التطبيق
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info(f"Starting server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
