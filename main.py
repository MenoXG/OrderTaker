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
    
    thread = threading.Thread(target=delete)
    thread.daemon = True
    thread.start()

# =============================
# 3. دالة للحصول على Access Token من SendPulse
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
# 5. إرسال رسالة للعميل عبر SendPulse
# =============================
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

# =============================
# 6. إرسال صورة للعميل عبر SendPulse
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
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            logger.info(f"Photo sent successfully to {channel} client {contact_id}")
            return True
        else:
            logger.error(f"Failed to send photo to {channel} {contact_id}: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error sending photo to {channel} client: {e}")
        return False

# =============================
# 7. إرسال رسالة إلى جروب تليجرام
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
# 8. التحقق من الطلبات المتأخرة
# =============================
def check_delayed_orders():
    try:
        logger.info("🔍 Checking delayed orders...")
        
        current_time = datetime.now()
        delayed_contacts = []

        for contact_id, scenarios in list(client_messages.items()):
            if 'order' in scenarios:
                order_data = scenarios['order']
                order_time = order_data['timestamp']
                time_diff = current_time - order_time
                
                # إذا مرت أكثر من 5 دقائق على الطلب
                if time_diff.total_seconds() > 300:
                    if 'delay_alert_sent' not in scenarios:
                        delayed_contacts.append(contact_id)
                        logger.info(f"🚨 Order for contact {contact_id} is DELAYED")

        # إرسال تنبيهات للطلبات المتأخرة
        for contact_id in delayed_contacts:
            if contact_id in client_messages and 'delay_alert_sent' not in client_messages[contact_id]:
                order_data = client_messages[contact_id]['order']
                channel = order_data.get('channel', 'telegram')
                
                delay_message = f"🚨 <b>تنبيه تأخر في التنفيذ</b>\n"
                delay_message += f"🆔 الرقم التعريفي: {contact_id}\n"
                delay_message += f"⏰ الوقت المنقضي: أكثر من 5 دقائق\n"
                delay_message += f"📞 القناة: {channel}\n"
                delay_message += f"🔔 تم إرسال الطلب في: {order_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}"
                
                success = send_scenario_message_to_telegram(delay_message, contact_id, channel, "delay")
                if success:
                    client_messages[contact_id]['delay_alert_sent'] = {'timestamp': datetime.now()}
                    logger.info(f"✅ Delay alert sent for contact: {contact_id}")
                
        logger.info(f"📊 Found {len(delayed_contacts)} delayed orders")
        
    except Exception as e:
        logger.error(f"❌ Error in check_delayed_orders: {e}")

# =============================
# 9. بدء مؤقت للتحقق من الطلبات المتأخرة
# =============================
def start_delayed_orders_checker():
    def checker_loop():
        logger.info("🔄 Starting delayed orders checker...")
        while True:
            try:
                check_delayed_orders()
                time.sleep(30)  # التحقق كل 30 ثانية
            except Exception as e:
                logger.error(f"❌ Error in delayed orders checker: {e}")
                time.sleep(30)
    
    thread = threading.Thread(target=checker_loop)
    thread.daemon = True
    thread.start()
    logger.info("✅ Delayed orders checker started")

# =============================
# 10. استقبال Webhook من SendPulse
# =============================
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        logger.info(f"📩 Received webhook data")

        if not data:
            return {"status": "error", "message": "No data received"}, 400

        contact_id = data.get("contact_id", "")
        channel = data.get("channel", "telegram")
        scenario = data.get("scenario", "order")
        neworder = data.get("neworder", "")

        if not contact_id:
            logger.error("❌ No contact_id received in webhook")
            return {"status": "error", "message": "No contact_id"}, 400

        logger.info(f"📝 Processing scenario: {scenario}, contact_id: {contact_id}")

        # بناء الرسالة من neworder فقط - بدون تنسيق
        if neworder:
            if isinstance(neworder, dict):
                formatted_order = json.dumps(neworder, ensure_ascii=False, indent=2)
            else:
                formatted_order = str(neworder)
        else:
            formatted_order = "لا توجد بيانات"

        # بناء الرسالة بناءً على السيناريو
        if scenario == "delay":
            message = f"🚨 <b>تنبيه تأخر في التنفيذ</b>\n{formatted_order}"
        elif scenario == "photo":
            message = f"📸 <b>طلب صورة إضافية من العميل</b>\n{formatted_order}"
        else:  # order
            message = f"📩 <b>طلب جديد</b>\n{formatted_order}"

        # إرسال الرسالة
        success = send_scenario_message_to_telegram(message, contact_id, channel, scenario)
        
        if success:
            return {"status": "ok"}, 200
        else:
            return {"status": "error", "message": "Failed to send to Telegram"}, 500
            
    except Exception as e:
        logger.error(f"❌ Error in webhook: {e}")
        return {"status": "error", "message": str(e)}, 500

# =============================
# 11. استقبال ضغط الأزرار + الصور من التليجرام
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

        if not data:
            return {"status": "ok"}, 200

        # التعامل مع الأزرار
        if "callback_query" in data:
            callback = data["callback_query"]
            query_id = callback["id"]
            chat_id = callback["message"]["chat"]["id"]
            message_id = callback["message"]["message_id"]
            callback_data = callback["data"]

            logger.info(f"🔄 Callback received: {callback_data}")

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
                send_to_client(contact_id, "✅ تم تنفيذ طلبك بنجاح", channel)
                edit_url = f"https://api.telegram.org/bot{token}/editMessageText"
                edit_payload = {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": "✅ تم تنفيذ الطلب بنجاح",
                    "parse_mode": "HTML"
                }
                requests.post(edit_url, json=edit_payload, timeout=30)
                delete_message_after_delay(chat_id, message_id, 5)
                
                # مسح من الذاكرة
                if contact_id in client_messages and scenario in client_messages[contact_id]:
                    del client_messages[contact_id][scenario]
                    if not client_messages[contact_id]:
                        del client_messages[contact_id]
                
            elif action == "cancel":
                send_to_client(contact_id, "❌ تم إلغاء طلبك.", channel)
                edit_url = f"https://api.telegram.org/bot{token}/editMessageText"
                edit_payload = {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": "❌ تم إلغاء الطلب",
                    "parse_mode": "HTML"
                }
                requests.post(edit_url, json=edit_payload, timeout=30)
                delete_message_after_delay(chat_id, message_id, 5)
                
                # مسح من الذاكرة
                if contact_id in client_messages and scenario in client_messages[contact_id]:
                    del client_messages[contact_id][scenario]
                    if not client_messages[contact_id]:
                        del client_messages[contact_id]
                
            elif action == "sendpic":
                pending_photos[str(chat_id)] = {
                    'contact_id': contact_id,
                    'channel': channel,
                    'scenario': scenario,
                    'request_message_id': message_id
                }
                edit_url = f"https://api.telegram.org/bot{token}/editMessageText"
                edit_payload = {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": "📷 من فضلك ارفع صورة في الجروب وسأقوم بإرسالها للعميل",
                    "parse_mode": "HTML"
                }
                requests.post(edit_url, json=edit_payload, timeout=30)

            elif action in ["transfer_minus", "transfer_plus"]:
                flow_type = action
                flow_name = "تحويل ناقص" if flow_type == "transfer_minus" else "تحويل زائد"
                
                success = run_flow(contact_id, channel, flow_type)
                if success:
                    confirmation_message = f"🔄 تم {flow_name} للطلب بنجاح"
                    send_to_client(contact_id, f"🔄 تم {flow_name} لطلبك وسيتم متابعته من قبل الفريق المختص", channel)
                else:
                    confirmation_message = f"❌ فشل {flow_name} للطلب"
                
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
                    delete_message_after_delay(chat_id, confirmation_message_id, 5)

        # التعامل مع الصور
        elif "message" in data and "photo" in data["message"]:
            message_data = data["message"]
            chat_id = message_data["chat"]["id"]
            message_id = message_data["message_id"]

            if str(chat_id) in pending_photos:
                pending_data = pending_photos.pop(str(chat_id))
                contact_id = pending_data['contact_id']
                channel = pending_data['channel']
                request_message_id = pending_data.get('request_message_id')

                # الحصول على الصورة
                photo = message_data["photo"][-1]
                file_id = photo["file_id"]

                file_info_url = f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}"
                file_info_response = requests.get(file_info_url, timeout=30)
                
                if file_info_response.status_code == 200:
                    file_info = file_info_response.json()
                    if file_info.get("ok"):
                        file_path = file_info["result"]["file_path"]
                        file_url = f"https://api.telegram.org/file/bot{token}/{file_path}"

                        # إرسال الصورة للعميل
                        success = send_photo_to_client(contact_id, file_url, channel)
                        
                        if success:
                            if request_message_id:
                                delete_telegram_message(chat_id, request_message_id)
                            delete_telegram_message(chat_id, message_id)
                            
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
                                delete_message_after_delay(chat_id, confirmation_message_id, 5)

        return {"status": "ok"}, 200
        
    except Exception as e:
        logger.error(f"❌ Error in Telegram webhook: {e}")
        return {"status": "error", "message": str(e)}, 500

# =============================
# 12. صفحات التحقق والإدارة
# =============================
@app.route("/")
def home():
    return {
        "status": "running",
        "service": "OrderTaker - Simplified Version",
        "timestamp": time.time(),
        "active_orders": len(client_messages)
    }

@app.route("/health")
def health():
    return {"status": "healthy", "timestamp": time.time(), "active_orders": len(client_messages)}, 200

@app.route("/active_orders")
def active_orders():
    try:
        orders_info = []
        current_time = datetime.now()
        
        for contact_id, scenarios in client_messages.items():
            if 'order' in scenarios:
                order_data = scenarios['order']
                time_diff = current_time - order_data['timestamp']
                orders_info.append({
                    'contact_id': contact_id,
                    'channel': order_data.get('channel', 'telegram'),
                    'timestamp': order_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                    'minutes_passed': int(time_diff.total_seconds() / 60),
                    'is_delayed': time_diff.total_seconds() > 300,
                    'has_delay_alert': 'delay_alert_sent' in scenarios
                })
        
        return {
            "status": "ok",
            "active_orders_count": len(orders_info),
            "orders": orders_info
        }
    except Exception as e:
        logger.error(f"❌ Error in active_orders: {e}")
        return {"status": "error", "message": str(e)}, 500

@app.route("/trigger_check")
def trigger_check():
    try:
        check_delayed_orders()
        return {"status": "ok", "message": "Delayed orders check triggered manually"}
    except Exception as e:
        logger.error(f"❌ Error in trigger_check: {e}")
        return {"status": "error", "message": str(e)}, 500

# =============================
# 13. بدء التطبيق
# =============================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info(f"🚀 Starting Simplified OrderTaker server on port {port}")
    
    # بدء نظام التحقق من الطلبات المتأخرة
    start_delayed_orders_checker()
    logger.info("✅ Delayed orders checker initialized")
    
    app.run(host="0.0.0.0", port=port, debug=False)
