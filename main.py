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
# 13. إرسال رسالة بسيطة إلى الجروب (زر واحد فقط - إرسال صورة)
# =============================
def send_simple_message_to_telegram(message, contact_id, channel):
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
            logger.info(f"Simple message sent to Telegram group with contact_id: {contact_id} and channel: {channel}")
            return True
        else:
            logger.error(f"Failed to send simple message to Telegram: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending simple message to Telegram: {e}")
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
        cash_control = data.get("CashControl", "")
        short_url = data.get("ShortUrl", "")
        much = data.get("much", "")
        platform = data.get("Platform", "")
        redid = data.get("redid", "")
        note = data.get("Note", "")
        contact_id = data.get("contact_id", "")
        channel = data.get("channel", "telegram")
        
        # ⚡ **استخدام scenario لتحديد نوع الطلب**
        scenario = data.get("scenario", "order")  # القيم: order, photo, delay
        
        # 🔍 **الحفاظ على التوافق مع الطريقة القديمة**
        complaint_reason = data.get("complaint_reason", "")

        if not contact_id:
            logger.error("No contact_id received in webhook")
            return {"status": "error", "message": "No contact_id"}, 400

        # ⚡ **معالجة أنواع الطلبات بناءً على scenario**
        if scenario == "delay":
            # بناء رسالة شكوى التأخر
            message_lines = ["🚨 <b>تنبيه تأخر في التنفيذ</b>"]
            
            if full_name:
                message_lines.append(f"العميل: {full_name}")
            if username:
                message_lines.append(f"التليجرام: @{username}")
            if redid:
                message_lines.append(f"الرقم التعريفي: {redid}")
            if complaint_reason:
                message_lines.append(f"سبب التأخر: {complaint_reason}")
            elif note:
                message_lines.append(f"سبب التأخر: {note}")
            elif not complaint_reason and not note:
                message_lines.append(f"سبب التأخر: غير محدد")
                
            message = "\n".join(message_lines)
            
            # إرسال رسالة شكوى التأخر (أزرار محددة)
            success = send_scenario_message_to_telegram(message, contact_id, channel, scenario)
            logger.info(f"Delay complaint processed for contact: {contact_id}")
            
        elif scenario == "photo":
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
            success = send_scenario_message_to_telegram(message, contact_id, channel, scenario)
            logger.info(f"Photo request processed for contact: {contact_id}")
            
        else:  # scenario == "order" (الافتراضي)
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
                    line += f"الرصيــد {much}")
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
            success = send_scenario_message_to_telegram(message, contact_id, channel, scenario)
            logger.info(f"New order processed for contact: {contact_id}")
        
        if success:
            return {"status": "ok"}, 200
        else:
            return {"status": "error", "message": "Failed to send to Telegram"}, 500
            
    except Exception as e:
        logger.error(f"Error in webhook: {e}")
        return {"status": "error", "message": str(e)}, 500

# =============================
# 15. إرسال رسالة إلى جروب تليجرام بناءً على السيناريو
# =============================
def send_scenario_message_to_telegram(message, contact_id, channel, scenario):
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
        
        # ⚡ **بناء الأزرار بناءً على نوع السيناريو**
        keyboard = {"inline_keyboard": []}
        
        if scenario == "order":
            # طلب جديد - جميع الأزرار
            keyboard["inline_keyboard"] = [
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
        elif scenario == "delay":
            # شكوى تأخر - زر فتح المحادثة وزر إرسال صورة
            keyboard["inline_keyboard"] = [
                [
                    {"text": "📷 إرسال صورة", "callback_data": f"sendpic:{contact_id}:{channel}"},
                ],
                [
                    {"text": "💬 فتح المحادثة", "url": sendpulse_url}
                ]
            ]
        elif scenario == "photo":
            # طلب صورة - زر إرسال صورة فقط
            keyboard["inline_keyboard"] = [
                [
                    {"text": "📷 إرسال صورة", "callback_data": f"sendpic:{contact_id}:{channel}"},
                ]
            ]
        else:
            # سيناريو غير معروف - نستخدم الأزرار الافتراضية (order)
            keyboard["inline_keyboard"] = [
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
        
        payload = {
            "chat_id": group_id,
            "text": message_with_channel,
            "parse_mode": "HTML",
            "reply_markup": keyboard
        }
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            logger.info(f"Message sent to Telegram group with contact_id: {contact_id}, channel: {channel}, scenario: {scenario}")
            return True
        else:
            logger.error(f"Failed to send to Telegram: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending to Telegram: {e}")
        return False

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
