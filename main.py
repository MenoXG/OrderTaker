import os
import requests
from flask import Flask, request
import logging
import time
import tempfile
import shutil
import threading
from datetime import datetime, timedelta
import re
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
        else:
            logger.error(f"❌ Failed to auto-delete message {message_id}")
    
    thread = threading.Thread(target=delete)
    thread.daemon = True
    thread.start()

# =============================
# 3. دالة التحقق من الطلبات المتأخرة وإرسال تنبيه - محسنة تماماً
# =============================
def check_delayed_orders():
    try:
        logger.info("🔍 Starting COMPREHENSIVE delayed orders check...")
        logger.info(f"📊 Total contacts in memory: {len(client_messages)}")
        
        current_time = datetime.now()
        delayed_contacts = []
        total_orders = 0

        # التحقق من جميع الطلبات النشطة
        for contact_id, scenarios in list(client_messages.items()):
            logger.info(f"  👤 Checking contact: {contact_id}")
            
            for scenario, scenario_data in scenarios.items():
                if scenario == 'order':  # نتحقق فقط من طلبات الطلبات الجديدة
                    total_orders += 1
                    order_time = scenario_data['timestamp']
                    time_diff = current_time - order_time
                    minutes_passed = int(time_diff.total_seconds() / 60)
                    
                    logger.info(f"    📝 Order found: {minutes_passed} minutes passed")
                    
                    # إذا مرت أكثر من 5 دقائق على الطلب ولم يتم إرسال تنبيه تأخر
                    if minutes_passed >= 5:  # تغيير من > إلى >= للتأكد
                        if 'delay_alert_sent' not in scenarios:
                            delayed_contacts.append({
                                'contact_id': contact_id,
                                'scenario_data': scenario_data,
                                'minutes_passed': minutes_passed
                            })
                            logger.info(f"    🚨 DELAYED ORDER: {contact_id} - {minutes_passed} minutes")
                        else:
                            logger.info(f"    ℹ️ Alert already sent for: {contact_id}")
                    else:
                        logger.info(f"    ✅ Order still fresh: {contact_id} - {minutes_passed} minutes")

        logger.info(f"📊 Check completed: {total_orders} total orders, {len(delayed_contacts)} delayed orders found")

        # إرسال تنبيهات للطلبات المتأخرة
        for delayed in delayed_contacts:
            contact_id = delayed['contact_id']
            scenario_data = delayed['scenario_data']
            minutes_passed = delayed['minutes_passed']
            
            # التحقق مرة أخرى قبل الإرسال
            if contact_id in client_messages and 'delay_alert_sent' not in client_messages[contact_id]:
                # بناء رسالة التنبيه
                channel = scenario_data.get('channel', 'telegram')
                
                delay_message = f"🚨 <b>تنبيه تأخر في التنفيذ</b>\n"
                delay_message += f"🆔 الرقم التعريفي: {contact_id}\n"
                delay_message += f"⏰ الوقت المنقضي: {minutes_passed} دقائق\n"
                delay_message += f"📞 القناة: {channel}\n"
                delay_message += f"🔔 تم إرسال الطلب في: {scenario_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}"
                
                # إرسال رسالة تنبيه التأخر
                success = send_scenario_message_to_telegram(delay_message, contact_id, channel, "delay")
                if success:
                    logger.info(f"✅ Delay alert sent successfully for contact: {contact_id}")
                    
                    # وضع علامة أن تنبيه التأخر تم إرساله
                    client_messages[contact_id]['delay_alert_sent'] = {
                        'timestamp': datetime.now(),
                        'alert_minutes': minutes_passed
                    }
                else:
                    logger.error(f"❌ Failed to send delay alert for contact: {contact_id}")
            else:
                logger.info(f"ℹ️ Delay alert already sent for contact: {contact_id}")
                
        logger.info(f"📊 Delayed orders processing completed. Sent {len(delayed_contacts)} alerts")
        
    except Exception as e:
        logger.error(f"❌ Error in check_delayed_orders: {e}")

# =============================
# 4. بدء مؤقت للتحقق من الطلبات المتأخرة - محسنة
# =============================
def start_delayed_orders_checker():
    def checker_loop():
        logger.info("🔄 Starting ENHANCED delayed orders checker loop...")
        check_count = 0
        while True:
            try:
                check_count += 1
                current_time = datetime.now().strftime('%H:%M:%S')
                logger.info(f"🔍 Delayed orders check #{check_count} at {current_time}")
                logger.info(f"📊 Current active contacts: {len(client_messages)}")
                
                # طباعة تفصيلية للطلبات النشطة
                if client_messages:
                    logger.info("📋 Active orders details:")
                    for contact_id, scenarios in client_messages.items():
                        for scenario, data in scenarios.items():
                            if scenario == 'order':
                                time_diff = datetime.now() - data['timestamp']
                                minutes_passed = int(time_diff.total_seconds() / 60)
                                has_alert = 'delay_alert_sent' in scenarios
                                logger.info(f"   - {contact_id}: {minutes_passed}m ago, alert: {has_alert}")
                else:
                    logger.info("📭 No active orders in memory")
                
                check_delayed_orders()
                
                # التحقق كل 30 ثانية
                time.sleep(30)
            except Exception as e:
                logger.error(f"❌ Error in delayed orders checker loop: {e}")
                time.sleep(30)
    
    thread = threading.Thread(target=checker_loop)
    thread.daemon = True
    thread.start()
    logger.info("✅ Enhanced delayed orders checker started successfully")

# =============================
# 5. إرسال رسالة إلى جروب تليجرام بناءً على السيناريو - محسنة للتتبع
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
            # شكوى تأخر - زر فتح المحادثة وزر إرسال صورة
            keyboard["inline_keyboard"] = [
                [
                    {"text": "📷 إرسال صورة", "callback_data": f"sendpic:{contact_id}:{channel}:delay"},
                ],
                [
                    {"text": "💬 فتح المحادثة", "url": sendpulse_url}
                ]
            ]
        elif scenario == "photo":
            # طلب صورة - زر إرسال صورة فقط
            keyboard["inline_keyboard"] = [
                [
                    {"text": "📷 إرسال صورة", "callback_data": f"sendpic:{contact_id}:{channel}:photo"},
                ]
            ]
        else:
            # سيناريو غير معروف - نستخدم الأزرار الافتراضية (order)
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
            result = response.json()
            message_id = result['result']['message_id']
            
            logger.info(f"✅ Telegram message sent: ID {message_id} for contact {contact_id}")
            
            # حفظ معرف الرسالة في الذاكرة لتتبع رسائل العميل مع الوقت
            if contact_id not in client_messages:
                client_messages[contact_id] = {}
            
            # حفظ بيانات السيناريو
            client_messages[contact_id][scenario] = {
                'message_id': message_id,
                'timestamp': datetime.now(),
                'channel': channel
            }
            
            logger.info(f"💾 Stored in memory: contact_id={contact_id}, scenario={scenario}, message_id={message_id}")
            logger.info(f"📊 Total contacts in memory: {len(client_messages)}")
            
            return True
        else:
            logger.error(f"❌ Failed to send to Telegram: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Error sending to Telegram: {e}")
        return False

# =============================
# 6. استقبال Webhook من SendPulse - محسنة للتتبع
# =============================
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        logger.info(f"📩 Received webhook data")

        if not data:
            return {"status": "error", "message": "No data received"}, 400

        # استخراج البيانات الأساسية من الـ webhook
        contact_id = data.get("contact_id", "")
        channel = data.get("channel", "telegram")
        scenario = data.get("scenario", "order")
        
        # ⚡ **استخراج البيانات الجديدة من متغير neworder**
        neworder = data.get("neworder", "")
        
        # 🔍 **الحفاظ على التوافق مع النظام القديم**
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
        complaint_reason = data.get("complaint_reason", "")

        if not contact_id:
            logger.error("❌ No contact_id received in webhook")
            return {"status": "error", "message": "No contact_id"}, 400

        logger.info(f"📝 Processing scenario: {scenario}, contact_id: {contact_id}")
        logger.info(f"📦 neworder data present: {bool(neworder)}")

        # ⚡ **معالجة أنواع الطلبات بناءً على scenario**
        if scenario == "delay":
            # بناء رسالة شكوى التأخر
            if neworder:
                # استخدام neworder كما هو بدون تنسيق
                if isinstance(neworder, dict):
                    formatted_order = json.dumps(neworder, ensure_ascii=False, indent=2)
                else:
                    formatted_order = str(neworder)
                message = f"🚨 <b>تنبيه تأخر في التنفيذ</b>\n{formatted_order}"
            else:
                # استخدام النظام القديم
                message_lines = ["🚨 <b>تنبيه تأخر في التنفيذ</b>"]
                
                if full_name:
                    message_lines.append(f"👤 العميل: {full_name}")
                if username:
                    message_lines.append(f"📱 التليجرام: @{username}")
                if redid:
                    message_lines.append(f"🆔 الرقم التعريفي: {redid}")
                if complaint_reason:
                    message_lines.append(f"📝 سبب التأخر: {complaint_reason}")
                elif note:
                    message_lines.append(f"📝 سبب التأخر: {note}")
                else:
                    message_lines.append(f"📝 سبب التأخر: غير محدد")
                    
                message = "\n".join(message_lines)
            
            # إرسال رسالة شكوى التأخر (أزرار محددة)
            success = send_scenario_message_to_telegram(message, contact_id, channel, scenario)
            logger.info(f"📨 Delay complaint processed for contact: {contact_id}")
            
        elif scenario == "photo":
            # بناء رسالة طلب الصورة الإضافية
            if neworder:
                # استخدام neworder كما هو بدون تنسيق
                if isinstance(neworder, dict):
                    formatted_order = json.dumps(neworder, ensure_ascii=False, indent=2)
                else:
                    formatted_order = str(neworder)
                message = f"📸 <b>طلب صورة إضافية من العميل</b>\n{formatted_order}"
            else:
                # استخدام النظام القديم
                message_lines = ["📸 <b>طلب صورة إضافية من العميل</b>"]
                
                if full_name:
                    message_lines.append(f"👤 العميل: {full_name}")
                if username:
                    message_lines.append(f"📱 التليجرام: @{username}")
                if redid:
                    message_lines.append(f"🆔 الرقم التعريفي: {redid}")
                if note:
                    message_lines.append(f"📝 الملاحظة: {note}")
                    
                message = "\n".join(message_lines)
            
            # إرسال رسالة طلب الصورة الإضافية (زر واحد فقط)
            success = send_scenario_message_to_telegram(message, contact_id, channel, scenario)
            logger.info(f"📨 Photo request processed for contact: {contact_id}")
            
        else:  # scenario == "order" (الافتراضي)
            # بناء رسالة الطلب الجديد
            if neworder:
                # استخدام neworder كما هو بدون تنسيق
                logger.info(f"📝 Using neworder data (type: {type(neworder)})")
                if isinstance(neworder, dict):
                    formatted_order = json.dumps(neworder, ensure_ascii=False, indent=2)
                else:
                    formatted_order = str(neworder)
                message = f"📩 <b>طلب جديد</b>\n{formatted_order}"
                logger.info(f"📝 Raw order data length: {len(formatted_order)} characters")
            else:
                # استخدام النظام القديم مع التنسيق العادي
                message_lines = []
                
                # إضافة الحقول التي تحتوي على قيم فقط بنفس التنسيق المطلوب
                if full_name or username:
                    line = ""
                    if full_name:
                        line += f"👤 العميل {full_name}"
                    if username:
                        if line:
                            line += f" 📱 تليجرام @{username}"
                        else:
                            line += f"📱 تليجرام @{username}"
                    message_lines.append(line)
                
                if agent or price_in:
                    line = ""
                    if agent:
                        line += f"🛒 شفــت {agent}"
                    if price_in:
                        if line:
                            line += f" 💰 سعـر البيـع {price_in}"
                        else:
                            line += f"💰 سعـر البيـع {price_in}"
                    message_lines.append(line)
                
                if much2 or paid_by:
                    line = ""
                    if much2:
                        line += f"💵 المبلـغ {much2}"
                    if paid_by:
                        if line:
                            line += f" 💳 جنيـه {paid_by}"
                        else:
                            line += f"💳 جنيـه {paid_by}"
                    message_lines.append(line)
                
                if cash_control:
                    message_lines.append(f"🏦 رقم/اسم المحفظـة {cash_control}")
                
                if short_url:
                    message_lines.append(f"🧾 الإيصـال {short_url}")
                
               if much or platform:
                    line = ""
                    if much:
                        line += f"💎 الرصيــد {much}"
                    if platform:
                        if line:
                            line += f" 💻 $ {platform}"
                        else:
                            line += f"💻 $ {platform}"
                    message_lines.append(line)
                
                if redid:
                    message_lines.append(f"🆔 {redid}")
                
                if note:
                    message_lines.append(f"📝 {note}")
                
                # إضافة عنوان الرسالة في الأعلى
                if message_lines:
                    message_lines.insert(0, "📩 <b>طلب جديد</b>")
                
                # دمج كل الأسطر في رسالة واحدة
                message = "\n".join(message_lines) if message_lines else "📩 <b>طلب جديد</b>"

            # إرسال رسالة الطلب الجديد (بجميع الأزرار)
            success = send_scenario_message_to_telegram(message, contact_id, channel, scenario)
            logger.info(f"📨 New order processed for contact: {contact_id}")
        
        if success:
            return {"status": "ok"}, 200
        else:
            return {"status": "error", "message": "Failed to send to Telegram"}, 500
            
    except Exception as e:
        logger.error(f"❌ Error in webhook: {e}")
        return {"status": "error", "message": str(e)}, 500

# =============================
# 7. صفحات المراقبة والتصحيح المحسنة
# =============================
@app.route("/active_orders")
def active_orders():
    try:
        orders_info = []
        current_time = datetime.now()
        
        for contact_id, scenarios in client_messages.items():
            for scenario, data in scenarios.items():
                if scenario == 'order':
                    time_diff = current_time - data['timestamp']
                    minutes_passed = int(time_diff.total_seconds() / 60)
                    has_alert = 'delay_alert_sent' in scenarios
                    
                    orders_info.append({
                        'contact_id': contact_id,
                        'scenario': scenario,
                        'message_id': data.get('message_id', 'N/A'),
                        'channel': data.get('channel', 'telegram'),
                        'timestamp': data['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                        'minutes_passed': minutes_passed,
                        'is_delayed': minutes_passed >= 5,
                        'has_delay_alert': has_alert
                    })
        
        return {
            "status": "ok",
            "active_orders_count": len(orders_info),
            "current_time": current_time.strftime('%Y-%m-%d %H:%M:%S'),
            "total_contacts_in_memory": len(client_messages),
            "orders": orders_info
        }
    except Exception as e:
        logger.error(f"❌ Error in active_orders: {e}")
        return {"status": "error", "message": str(e)}, 500

@app.route("/debug_memory")
def debug_memory():
    try:
        debug_info = {}
        for contact_id, scenarios in client_messages.items():
            debug_info[contact_id] = {}
            for scenario, data in scenarios.items():
                if scenario == 'order':
                    time_diff = datetime.now() - data['timestamp']
                    debug_info[contact_id][scenario] = {
                        'minutes_old': int(time_diff.total_seconds() / 60),
                        'timestamp': data['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                        'channel': data.get('channel', 'telegram')
                    }
                elif scenario == 'delay_alert_sent':
                    debug_info[contact_id][scenario] = {
                        'alert_minutes': data.get('alert_minutes', 'N/A'),
                        'timestamp': data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
                    }
        
        return {
            "status": "ok",
            "total_contacts": len(client_messages),
            "memory_contents": debug_info
        }
    except Exception as e:
        logger.error(f"❌ Error in debug_memory: {e}")
        return {"status": "error", "message": str(e)}, 500

@app.route("/trigger_check")
def trigger_check():
    try:
        logger.info("🔔 Manual delayed orders check triggered via API")
        check_delayed_orders()
        return {
            "status": "ok", 
            "message": "Delayed orders check triggered manually",
            "active_contacts": len(client_messages)
        }
    except Exception as e:
        logger.error(f"❌ Error in trigger_check: {e}")
        return {"status": "error", "message": str(e)}, 500

@app.route("/clear_orders")
def clear_orders():
    try:
        orders_count = len(client_messages)
        client_messages.clear()
        logger.info(f"🧹 Cleared all {orders_count} orders from memory")
        return {
            "status": "ok",
            "message": f"Cleared {orders_count} orders from memory",
            "cleared_count": orders_count
        }
    except Exception as e:
        logger.error(f"❌ Error clearing orders: {e}")
        return {"status": "error", "message": str(e)}, 500

# =============================
# 8. بدء التطبيق
# =============================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info(f"🚀 Starting Enhanced OrderTaker server on port {port}")
    
    # بدء نظام التحقق من الطلبات المتأخرة
    start_delayed_orders_checker()
    logger.info("✅ Enhanced delayed orders checker initialized")
    
    app.run(host="0.0.0.0", port=port, debug=False)
