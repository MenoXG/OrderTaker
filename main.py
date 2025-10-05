import os
import requests
from flask import Flask, request
import logging
import time
import tempfile
import shutil
import threading
from datetime import datetime, timedelta
import json
import base64

# إعداد logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ذاكرة مؤقتة (chat_id → {contact_id, channel, request_message_id})
pending_photos = {}

# ذاكرة لتتبع رسائل العملاء (contact_id → {scenario: message_id, timestamp})
client_messages = {}

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
            logger.info(f"✅ Message {message_id} deleted successfully from chat {chat_id}")
            return True
        else:
            logger.error(f"❌ Failed to delete message {message_id}: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Error deleting message: {e}")
        return False

# =============================
# 2. دالة مسح رسالة بعد تأخير
# =============================
def delete_message_after_delay(chat_id, message_id, delay_seconds):
    def delete():
        time.sleep(delay_seconds)
        success = delete_telegram_message(chat_id, message_id)
        if success:
            logger.info(f"🗑️ Auto-deleted message {message_id} after {delay_seconds} seconds")
        else:
            logger.error(f"❌ Failed to auto-delete message {message_id}")
    
    thread = threading.Thread(target=delete)
    thread.daemon = True
    thread.start()

# =============================
# 3. دالة تحميل الصورة وإنشاء رابط مؤقت - محسنة
# =============================
def download_and_create_temp_url(file_url, token, contact_id):
    try:
        logger.info(f"📥 Starting photo download from: {file_url}")
        
        # تحميل الصورة من Telegram
        response = requests.get(file_url, stream=True, timeout=30)
        
        if response.status_code == 200:
            # إنشاء ملف مؤقت في الذاكرة
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                for chunk in response.iter_content(chunk_size=8192):
                    temp_file.write(chunk)
                temp_path = temp_file.name
            
            logger.info(f"✅ Photo downloaded successfully: {temp_path}")
            
            try:
                # محاولة الرفع إلى tmpfiles.org
                with open(temp_path, 'rb') as f:
                    files = {'file': f}
                    upload_response = requests.post(
                        'https://tmpfiles.org/api/v1/upload',
                        files=files,
                        timeout=30
                    )
                
                # تنظيف الملف المؤقت
                os.unlink(temp_path)
                
                if upload_response.status_code == 200:
                    upload_data = upload_response.json()
                    if upload_data.get('status') == 'success':
                        download_url = upload_data['data']['url']
                        direct_url = download_url.replace('tmpfiles.org/', 'tmpfiles.org/dl/')
                        logger.info(f"✅ Temporary URL created: {direct_url}")
                        return direct_url
                    else:
                        logger.error(f"❌ Upload failed: {upload_data}")
                        return None
                else:
                    logger.error(f"❌ Upload failed with status: {upload_response.status_code}")
                    return None
                    
            except Exception as upload_error:
                logger.error(f"❌ Error uploading to tmpfiles.org: {upload_error}")
                # تنظيف الملف في حالة الخطأ
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                return None
                
        else:
            logger.error(f"❌ Failed to download photo: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error in download_and_create_temp_url: {e}")
        # تنظيف الملف في حالة الخطأ
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.unlink(temp_path)
        return None

# =============================
# 4. دالة بديلة لتحميل الصورة باستخدام imgbb
# =============================
def upload_to_imgbb(image_bytes):
    try:
        # تحويل الصورة إلى base64
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')
        
        # استخدام imgbb API (مجاني)
        api_key = "your_imgbb_api_key"  # يمكنك الحصول على مفتاح مجاني من imgbb.com
        url = "https://api.imgbb.com/1/upload"
        
        payload = {
            "key": api_key,
            "image": image_b64,
            "expiration": 600  # 10 دقائق
        }
        
        response = requests.post(url, data=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                image_url = result["data"]["url"]
                logger.info(f"✅ Image uploaded to imgbb: {image_url}")
                return image_url
            else:
                logger.error(f"❌ imgbb upload failed: {result}")
                return None
        else:
            logger.error(f"❌ imgbb upload failed with status: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error uploading to imgbb: {e}")
        return None

# =============================
# 5. إرسال صورة للعميل عبر SendPulse - محسنة
# =============================
def send_photo_to_client(contact_id, photo_url, channel):
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
            logger.error(f"Unknown channel for photo sending: {channel}")
            return False

        headers = {"Authorization": f"Bearer {token}"}
        logger.info(f"📤 Sending photo to {channel} client {contact_id}")
        logger.info(f"📎 Photo URL: {photo_url}")
        
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        logger.info(f"📨 SendPulse response status: {response.status_code}")
        
        if response.status_code == 200:
            logger.info(f"✅ Photo sent successfully to {channel} client {contact_id}")
            return True
        else:
            logger.error(f"❌ Failed to send photo to {channel} {contact_id}: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Error sending photo to {channel} client: {e}")
        return False

# =============================
# 6. إرسال رسالة إلى جروب تليجرام
# =============================
def send_scenario_message_to_telegram(message, contact_id, channel, scenario):
    try:
        token = os.getenv("TELEGRAM_TOKEN")
        group_id = os.getenv("GROUP_ID")

        if not token or not group_id:
            logger.error("TELEGRAM_TOKEN or GROUP_ID not set")
            return False

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        
        # إنشاء رابط SendPulse
        sendpulse_url = f"https://login.sendpulse.com/chatbots/chats?contact_id={contact_id}&channel={channel}"
        
        # إضافة رمز القناة إلى الرسالة
        channel_icon = "📱" if channel == "messenger" else "✈️"
        message_with_channel = f"{channel_icon} {message}"
        
        # بناء الأزرار بناءً على نوع السيناريو
        keyboard = {"inline_keyboard": []}
        
        if scenario == "order":
            keyboard["inline_keyboard"] = [
                [
                    {"text": "✅ تم التنفيذ", "callback_data": f"done:{contact_id}:{channel}:order"},
                    {"text": "❌ إلغاء", "callback_data": f"cancel:{contact_id}:{channel}:order"},
                ],
                [
                    {"text": "📷 إرسال صورة", "callback_data": f"sendpic:{contact_id}:{channel}:order"},
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
            keyboard["inline_keyboard"] = [
                [
                    {"text": "📷 إرسال صورة", "callback_data": f"sendpic:{contact_id}:{channel}:delay"},
                ],
                [
                    {"text": "💬 فتح المحادثة", "url": sendpulse_url}
                ]
            ]
        elif scenario == "photo":
            keyboard["inline_keyboard"] = [
                [
                    {"text": "📷 إرسال صورة", "callback_data": f"sendpic:{contact_id}:{channel}:photo"},
                ]
            ]
        else:
            keyboard["inline_keyboard"] = [
                [
                    {"text": "✅ تم التنفيذ", "callback_data": f"done:{contact_id}:{channel}:order"},
                    {"text": "❌ إلغاء", "callback_data": f"cancel:{contact_id}:{channel}:order"},
                ],
                [
                    {"text": "📷 إرسال صورة", "callback_data": f"sendpic:{contact_id}:{channel}:order"},
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
            message_id = response.json()['result']['message_id']
            
            # حفظ في الذاكرة لتتبع الطلبات
            if contact_id not in client_messages:
                client_messages[contact_id] = {}
            
            client_messages[contact_id][scenario] = {
                'message_id': message_id,
                'timestamp': datetime.now(),
                'channel': channel
            }
            
            logger.info(f"✅ Message sent and stored: contact_id={contact_id}, scenario={scenario}")
            return True
        else:
            logger.error(f"❌ Failed to send to Telegram: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Error sending to Telegram: {e}")
        return False

# =============================
# 7. استقبال ضغط الأزرار + الصور من التليجرام - محسنة تماماً
# =============================
@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    try:
        token = os.getenv("TELEGRAM_TOKEN")
        group_id = os.getenv("GROUP_ID")

        if not token:
            logger.error("❌ TELEGRAM_TOKEN not set")
            return {"status": "error"}, 500

        data = request.get_json()
        logger.info(f"📨 Received Telegram update")

        if not data:
            return {"status": "ok"}, 200

        # التعامل مع الأزرار
        if "callback_query" in data:
            callback = data["callback_query"]
            query_id = callback["id"]
            chat_id = callback["message"]["chat"]["id"]
            message_id = callback["message"]["message_id"]
            callback_data = callback["data"]

            logger.info(f"🔄 Callback received: {callback_data} from chat {chat_id}")

            # الرد على callback query
            requests.post(
                f"https://api.telegram.org/bot{token}/answerCallbackQuery",
                json={"callback_query_id": query_id},
                timeout=30
            )

            # تقسيم callback_data
            parts = callback_data.split(':')
            action = parts[0]
            contact_id = parts[1]
            channel = parts[2] if len(parts) > 2 else 'telegram'
            scenario = parts[3] if len(parts) > 3 else 'order'

            # معالجة الإجراءات
            if action == "done":
                # إرسال تأكيد للعميل
                send_to_client(contact_id, "✅ تم تنفيذ طلبك بنجاح", channel)
                
                # تعديل الرسالة الأصلية
                edit_url = f"https://api.telegram.org/bot{token}/editMessageText"
                edit_payload = {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": "✅ تم تنفيذ الطلب بنجاح",
                    "parse_mode": "HTML"
                }
                edit_response = requests.post(edit_url, json=edit_payload, timeout=30)
                
                if edit_response.status_code == 200:
                    # حذف الرسالة بعد 5 ثواني
                    delete_message_after_delay(chat_id, message_id, 5)
                    logger.info(f"🗑️ Scheduled deletion for message {message_id}")
                    
                    # مسح من الذاكرة
                    if contact_id in client_messages and scenario in client_messages[contact_id]:
                        del client_messages[contact_id][scenario]
                        if not client_messages[contact_id]:
                            del client_messages[contact_id]
                        logger.info(f"🧹 Removed {scenario} from memory for {contact_id}")
                else:
                    logger.error(f"❌ Failed to edit message: {edit_response.status_code}")
                
            elif action == "cancel":
                # إرسال تأكيد إلغاء للعميل
                send_to_client(contact_id, "❌ تم إلغاء طلبك.", channel)
                
                # تعديل الرسالة الأصلية
                edit_url = f"https://api.telegram.org/bot{token}/editMessageText"
                edit_payload = {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": "❌ تم إلغاء الطلب",
                    "parse_mode": "HTML"
                }
                edit_response = requests.post(edit_url, json=edit_payload, timeout=30)
                
                if edit_response.status_code == 200:
                    # حذف الرسالة بعد 5 ثواني
                    delete_message_after_delay(chat_id, message_id, 5)
                    logger.info(f"🗑️ Scheduled deletion for message {message_id}")
                    
                    # مسح من الذاكرة
                    if contact_id in client_messages and scenario in client_messages[contact_id]:
                        del client_messages[contact_id][scenario]
                        if not client_messages[contact_id]:
                            del client_messages[contact_id]
                        logger.info(f"🧹 Removed {scenario} from memory for {contact_id}")
                else:
                    logger.error(f"❌ Failed to edit message: {edit_response.status_code}")
                
            elif action == "sendpic":
                # حفظ طلب إرسال الصورة
                pending_photos[str(chat_id)] = {
                    'contact_id': contact_id,
                    'channel': channel,
                    'scenario': scenario,
                    'request_message_id': message_id
                }
                
                # تعديل الرسالة لتظهر طلب رفع الصورة
                edit_url = f"https://api.telegram.org/bot{token}/editMessageText"
                edit_payload = {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": "📷 من فضلك ارفع الصورة الآن في هذه المحادثة وسأقوم بإرسالها للعميل",
                    "parse_mode": "HTML"
                }
                edit_response = requests.post(edit_url, json=edit_payload, timeout=30)
                
                if edit_response.status_code == 200:
                    logger.info(f"✅ Photo request message updated for chat {chat_id}")
                else:
                    logger.error(f"❌ Failed to update photo request message: {edit_response.status_code}")

            elif action in ["transfer_minus", "transfer_plus"]:
                flow_type = action
                flow_name = "تحويل ناقص" if flow_type == "transfer_minus" else "تحويل زائد"
                
                success = run_flow(contact_id, channel, flow_type)
                if success:
                    confirmation_message = f"🔄 تم {flow_name} للطلب بنجاح"
                    send_to_client(contact_id, f"🔄 تم {flow_name} لطلبك وسيتم متابعته من قبل الفريق المختص", channel)
                else:
                    confirmation_message = f"❌ فشل {flow_name} للطلب"
                
                # إرسال رسالة تأكيد
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
                    # حذف رسالة التأكيد بعد 5 ثواني
                    delete_message_after_delay(chat_id, confirmation_message_id, 5)
                    logger.info(f"🗑️ Scheduled deletion for confirmation message {confirmation_message_id}")
                else:
                    logger.error(f"❌ Failed to send confirmation message")

        # التعامل مع الصور - الجزء المحسّن
        elif "message" in data and "photo" in data["message"]:
            message_data = data["message"]
            chat_id = message_data["chat"]["id"]
            message_id = message_data["message_id"]

            logger.info(f"🖼️ Photo received in chat {chat_id}, message_id: {message_id}")

            if str(chat_id) in pending_photos:
                pending_data = pending_photos.pop(str(chat_id))
                contact_id = pending_data['contact_id']
                channel = pending_data['channel']
                scenario = pending_data['scenario']
                request_message_id = pending_data.get('request_message_id')

                logger.info(f"🔄 Processing photo for contact {contact_id} on channel {channel}")

                # الحصول على أعلى دقة للصورة
                photo = message_data["photo"][-1]
                file_id = photo["file_id"]

                # الحصول على معلومات الملف
                file_info_url = f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}"
                file_info_response = requests.get(file_info_url, timeout=30)
                
                if file_info_response.status_code == 200:
                    file_info = file_info_response.json()
                    if file_info.get("ok"):
                        file_path = file_info["result"]["file_path"]
                        file_url = f"https://api.telegram.org/file/bot{token}/{file_path}"

                        logger.info(f"📎 Telegram file URL: {file_url}")
                        
                        # 1. تحميل الصورة وإنشاء رابط مؤقت
                        temp_photo_url = download_and_create_temp_url(file_url, token, contact_id)
                        
                        if temp_photo_url:
                            # 2. إرسال الصورة للعميل
                            success = send_photo_to_client(contact_id, temp_photo_url, channel)
                            
                            if success:
                                logger.info(f"✅ Photo sent successfully to client {contact_id}")
                                
                                # 3. مسح الرسائل بعد النجاح
                                
                                # مسح رسالة طلب الصورة (إذا كانت موجودة)
                                if request_message_id:
                                    delete_success = delete_telegram_message(chat_id, request_message_id)
                                    if delete_success:
                                        logger.info(f"🗑️ Deleted photo request message {request_message_id}")
                                    else:
                                        logger.error(f"❌ Failed to delete photo request message {request_message_id}")
                                
                                # مسح الصورة المرسلة في الجروب
                                delete_success = delete_telegram_message(chat_id, message_id)
                                if delete_success:
                                    logger.info(f"🗑️ Deleted uploaded photo message {message_id}")
                                else:
                                    logger.error(f"❌ Failed to delete uploaded photo message {message_id}")
                                
                                # 4. إرسال رسالة تأكيد
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
                                    # حذف رسالة التأكيد بعد 5 ثواني
                                    delete_message_after_delay(chat_id, confirmation_message_id, 5)
                                    logger.info(f"🗑️ Scheduled deletion for confirmation message {confirmation_message_id}")
                                else:
                                    logger.error(f"❌ Failed to send confirmation message")
                                
                            else:
                                logger.error(f"❌ Failed to send photo to client {contact_id}")
                                # إرسال رسالة خطأ
                                requests.post(
                                    f"https://api.telegram.org/bot{token}/sendMessage",
                                    json={
                                        "chat_id": chat_id,
                                        "text": f"❌ فشل إرسال الصورة للعميل"
                                    },
                                    timeout=30
                                )
                        else:
                            logger.error("❌ Failed to create temporary photo URL")
                            # إرسال رسالة خطأ
                            requests.post(
                                f"https://api.telegram.org/bot{token}/sendMessage",
                                json={
                                    "chat_id": chat_id,
                                    "text": f"❌ فشل تحميل الصورة، حاول مرة أخرى"
                                },
                                timeout=30
                            )
                    else:
                        logger.error(f"❌ File info not OK: {file_info}")
                else:
                    logger.error(f"❌ Failed to get file info: {file_info_response.status_code}")
            else:
                logger.info(f"ℹ️ Photo received but no pending request for chat {chat_id}")

        return {"status": "ok"}, 200
        
    except Exception as e:
        logger.error(f"❌ Error in Telegram webhook: {e}")
        return {"status": "error", "message": str(e)}, 500

# =============================
# 8. دوال الخدمات الأخرى (تبقى كما هي)
# =============================
def get_sendpulse_token():
    try:
        client_id = os.getenv("SENDPULSE_API_ID")
        client_secret = os.getenv("SENDPULSE_API_SECRET")
        
        if not client_id or not client_secret:
            logger.error("SendPulse API credentials not set")
            return None
            
        url = "https://api.sendpulse.com/oauth/access_token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret
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

def send_to_client(contact_id, text, channel):
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
            logger.error(f"Unknown channel: {channel}")
            return False

        headers = {"Authorization": f"Bearer {token}"}
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            logger.info(f"Message sent to {channel} client {contact_id}")
            return True
        else:
            logger.error(f"Failed to send message to {channel} {contact_id}: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error sending to {channel} client: {e}")
        return False

def run_flow(contact_id, channel, flow_type):
    try:
        token = get_sendpulse_token()
        if not token:
            logger.error("No token available for SendPulse")
            return False

        if channel == "telegram":
            url = "https://api.sendpulse.com/telegram/flows/run"
        elif channel == "messenger":
            url = "https://api.sendpulse.com/messenger/flows/run"
        else:
            logger.error(f"Unknown channel for flow: {channel}")
            return False

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
        
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
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
# 9. بدء التطبيق
# =============================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info(f"🚀 Starting Photo-Fixed OrderTaker server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
