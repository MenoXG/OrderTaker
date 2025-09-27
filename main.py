import os
import re
import logging
from flask import Flask, jsonify
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, CallbackQueryHandler, ContextTypes
import asyncio
from threading import Thread
from datetime import datetime

# إعداد logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# متغيرات البيئة
BOT_TOKEN = os.environ.get('BOT_TOKEN')
TELEGRAM_GROUP_ID = os.environ.get('TELEGRAM_GROUP_ID')
PORT = int(os.environ.get('PORT', 8000))

# تخزين البوت والتطبيق
bot = None
application = None
processed_messages = set()

class SendPulseMessageParser:
    """محلل رسائل SendPulse الخاص"""
    
    @staticmethod
    def is_sendpulse_message(text):
        """التعرف على رسائل SendPulse بناءً على الهيكل"""
        patterns = [
            r'العميل\s+[^\n]+\nشفت\s+[^\n]+\n[\s\S]*?الإيمال',
            r'العميل\s+[^\n]+\n[\s\S]*?Vodafone',
            r'سعر البيع\s+[\d\.]+\s+المبلغ\s+[\d\.]+\s+جنيه',
            r'SendPulse Notifications'
        ]
        
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
                return True
        return False
    
    @staticmethod
    def parse_message(text):
        """استخراج المعلومات من رسالة SendPulse"""
        try:
            data = {
                'client_name': 'غير معروف',
                'product': 'غير معروف',
                'sale_price': 'غير معروف',
                'amount': 'غير معروف',
                'payment_method': 'غير معروف',
                'email_link': 'غير معروف',
                'payment_id': 'غير معروف',
                'wallet_info': 'غير معروف'
            }
            
            # استخراج اسم العميل
            client_match = re.search(r'العميل\s+([^\n]+)', text)
            if client_match:
                data['client_name'] = client_match.group(1).strip()
            
            # استخراج معلومات المنتج والسعر
            product_match = re.search(r'شفت\s+([^\n]+)\s+سعر البيع\s+([\d\.]+)\s+المبلغ\s+([\d\.]+)\s+جنيه', text)
            if product_match:
                data['product'] = product_match.group(1).strip()
                data['sale_price'] = product_match.group(2).strip()
                data['amount'] = product_match.group(3).strip()
            
            # استخراج طريقة الدفع
            payment_match = re.search(r'جنيه\s+([^\n]+)', text)
            if payment_match:
                data['payment_method'] = payment_match.match.group(1).strip() if payment_match else 'غير معروف'
            
            # استخراج رابط الإيميل
            email_match = re.search(r'الإيمال[^\n]*\n([^\n]+)', text)
            if email_match:
                data['email_link'] = email_match.group(1).strip()
            
            # استخراج معلومات المحفظة
            wallet_match = re.search(r'رقم\s*/\s*اسم المعفظة\s*(\d+)', text)
            if wallet_match:
                data['wallet_info'] = wallet_match.group(1).strip()
            
            # استخراج معرف الدفع
            payment_id_match = re.search(r'(\d{9,10})', text)
            if payment_id_match:
                data['payment_id'] = payment_id_match.group(1).strip()
            
            return data
            
        except Exception as e:
            logger.error(f"Error parsing SendPulse message: {e}")
            return None

def create_order_keyboard(order_id):
    """إنشاء أزرار خاصة بطلبات SendPulse"""
    keyboard = [
        [
            InlineKeyboardButton("✅ تأكيد الاستلام", callback_data=f"confirm_{order_id}"),
            InlineKeyboardButton("📞 تواصل مع العميل", callback_data=f"contact_{order_id}")
        ],
        [
            InlineKeyboardButton("⚠️ بلاغ مشكلة", callback_data=f"problem_{order_id}"),
            InlineKeyboardButton("⏱ تأجيل المعالجة", callback_data=f"delay_{order_id}")
        ],
        [
            InlineKeyboardButton("💰 تأكيد التحويل", callback_data=f"transfer_{order_id}"),
            InlineKeyboardButton("📋 تفاصيل الطلب", callback_data=f"details_{order_id}")
        ],
        [
            InlineKeyboardButton("🎯 تم الإكمال", callback_data=f"complete_{order_id}"),
            InlineKeyboardButton("❌ حذف الطلب", callback_data=f"delete_{order_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def format_order_message(parsed_data, original_text, message_id):
    """تنسيق رسالة الطلب بشكل منظم"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    message = f"""
🛒 **طلب جديد - SendPulse**

👤 **العميل:** {parsed_data['client_name']}
📦 **المنتج:** {parsed_data['product']}
💰 **سعر البيع:** {parsed_data['sale_price']}
💵 **المبلغ:** {parsed_data['amount']} جنيه
🏦 **طريقة الدفع:** {parsed_data['payment_method']}
📧 **الرابط:** {parsed_data['email_link']}
🔢 **المعرف:** {parsed_data['payment_id']}
👛 **المحفظة:** {parsed_data['wallet_info']}

---
🆔 **رقم الرسالة:** {message_id}
⏰ **الوقت:** {timestamp}
📡 **المصدر:** SendPulse Bot
    """.strip()
    
    return message

async def handle_group_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل في الجروب والتعرف على رسائل SendPulse"""
    try:
        message = update.message
        
        # التأكد من أن الرسالة في الجروب المطلوب
        if str(message.chat.id) != TELEGRAM_GROUP_ID:
            return
        
        # تجاهل الرسائل من البوت نفسه
        if message.from_user and message.from_user.id == bot.id:
            return
        
        # تجنب معالجة الرسالة أكثر من مرة
        if message.message_id in processed_messages:
            return
        processed_messages.add(message.message_id)
        
        # الحصول على نص الرسالة
        if not message.text:
            return
        
        text = message.text
        
        # التحقق إذا كانت رسالة SendPulse
        if not SendPulseMessageParser.is_sendpulse_message(text):
            return
        
        logger.info(f"تم التعرف على رسالة SendPulse: {message.message_id}")
        
        # تحليل الرسالة
        parsed_data = SendPulseMessageParser.parse_message(text)
        
        if not parsed_data:
            parsed_data = {
                'client_name': 'غير معروف',
                'product': 'غير معروف', 
                'sale_price': 'غير معروف',
                'amount': 'غير معروف',
                'payment_method': 'غير معروف',
                'email_link': 'غير معروف',
                'payment_id': 'غير معروف',
                'wallet_info': 'غير معروف'
            }
        
        # استخدام المعرف الموجود أو إنشاء جديد
        order_id = parsed_data['payment_id'] if parsed_data['payment_id'] != 'غير معروف' else f"MSG{message.message_id}"
        
        # تنسيق الرسالة الجديدة
        formatted_message = format_order_message(parsed_data, text, message.message_id)
        
        # إرسال الرسالة المعدلة مع الأزرار
        await bot.send_message(
            chat_id=TELEGRAM_GROUP_ID,
            text=formatted_message,
            reply_markup=create_order_keyboard(order_id),
            parse_mode='Markdown'
        )
        
        logger.info(f"تم إعادة إرسال طلب SendPulse: {order_id}")
        
    except Exception as e:
        logger.error(f"خطأ في معالجة رسالة SendPulse: {e}")

async def handle_order_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إجراءات الطلبات"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    callback_data = query.data
    
    # استخراج الإجراء والمعرف
    if '_' in callback_data:
        action, order_id = callback_data.split('_', 1)
    else:
        action = callback_data
        order_id = "غير معروف"
    
    # ردود الإجراءات
    actions = {
        "confirm": "✅ تم تأكيد استلام الطلب",
        "contact": "📞 سيتم التواصل مع العميل",
        "problem": "⚠️ تم الإبلاغ عن مشكلة في الطلب",
        "delay": "⏱ تم تأجيل معالجة الطلب",
        "transfer": "💰 تم تأكيد التحويل المالي",
        "details": "📋 عرض تفاصيل الطلب الكاملة",
        "complete": "🎯 تم إكمال الطلب بنجاح",
        "delete": "❌ تم حذف الطلب"
    }
    
    response_text = actions.get(action, "إجراء غير معروف")
    
    # تحديث الرسالة الأصلية
    original_text = query.message.text
    user_action_text = f"\n\n---\n🔹 **الإجراء:** {response_text}\n👤 **المسؤول:** {user.first_name}\n🆔 **رقم الطلب:** {order_id}"
    
    if action == "delete":
        new_text = f"❌ **تم حذف الطلب**\n\n👤 المسؤول: {user.first_name}\n🆔 رقم الطلب: {order_id}"
        await query.edit_message_text(text=new_text, parse_mode='Markdown')
    elif action == "details":
        # إظهار تفاصيل إضافية
        new_text = original_text + f"\n\n📋 **التفاصيل الإضافية:**\n• تم استعراض الطلب بواسطة: {user.first_name}\n• وقت المعالجة: {datetime.now().strftime('%H:%M:%S')}"
        await query.edit_message_text(text=new_text, parse_mode='Markdown')
    else:
        new_text = original_text + user_action_text
        await query.edit_message_text(
            text=new_text,
            reply_markup=None,
            parse_mode='Markdown'
        )
    
    logger.info(f"المستخدم {user.id} قام بالإجراء {action} على الطلب {order_id}")

async def setup_bot():
    """إعداد البوت والتطبيق"""
    global bot, application
    
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN غير مضبوط في متغيرات البيئة")
        return
    
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        bot = application.bot
        
        # إضافة handler لمراقبة الرسائل في الجروب
        application.add_handler(MessageHandler(
            filters.Chat(chat_id=int(TELEGRAM_GROUP_ID)) & filters.TEXT,
            handle_group_messages
        ))
        
        # معالج إجراءات الطلبات
        application.add_handler(CallbackQueryHandler(handle_order_actions))
        
        logger.info("تم إعداد بوت SendPulse بنجاح")
        
    except Exception as e:
        logger.error(f"خطأ في إعداد البوت: {e}")

@app.route('/health', methods=['GET'])
def health_check():
    """فحص صحة التطبيق"""
    return jsonify({
        "status": "healthy", 
        "service": "SendPulse Order Manager Bot",
        "function": "إعادة توجيه طلبات SendPulse مع أزرار تفاعلية"
    })

@app.route('/test-parser', methods=['POST'])
def test_parser():
    """اختبار محلل رسائل SendPulse"""
    try:
        data = request.get_json()
        test_text = data.get('text', '')
        
        is_sendpulse = SendPulseMessageParser.is_sendpulse_message(test_text)
        parsed_data = SendPulseMessageParser.parse_message(test_text) if is_sendpulse else None
        
        return jsonify({
            "is_sendpulse_message": is_sendpulse,
            "parsed_data": parsed_data
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def run_bot():
    """تشغيل البوت في thread منفصل"""
    asyncio.run(setup_bot())
    if application:
        application.run_polling()

if __name__ == '__main__':
    # تشغيل البوت في thread منفصل
    bot_thread = Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # تشغيل تطبيق Flask
    app.run(host='0.0.0.0', port=PORT, debug=False)
