import os
import logging
import requests
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
import asyncio

# إعداد logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# متغيرات البيئة
BOT_TOKEN = os.environ.get('BOT_TOKEN')
TELEGRAM_GROUP_ID = os.environ.get('TELEGRAM_GROUP_ID')
SENDPULSE_CHANNEL_ID = os.environ.get('SENDPULSE_CHANNEL_ID', '@sendpulse_notifications')  # معرف القناة

class SendPulseMonitor:
    def __init__(self):
        self.bot = Bot(token=BOT_TOKEN)
        self.last_message_id = 0
        
    def create_keyboard(self):
        """إنشاء أزرار تفاعلية"""
        keyboard = [
            [
                InlineKeyboardButton("✅ تم التعامل", callback_data="done"),
                InlineKeyboardButton("⏱ مؤجل", callback_data="later")
            ],
            [
                InlineKeyboardButton("📞 اتصل بالعميل", callback_data="call"),
                InlineKeyboardButton("🗑 حذف الطلب", callback_data="delete")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    async def get_channel_messages(self):
        """الحصول على رسائل القناة باستخدام الـ API"""
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                if data['ok']:
                    return data['result']
            return []
            
        except Exception as e:
            logger.error(f"❌ خطأ في الحصول على الرسائل: {e}")
            return []
    
    def is_sendpulse_message(self, message_text):
        """التعرف على رسائل SendPulse"""
        keywords = [
            "SendPulse Notifications", "سعر البيع", "شفت", "جنيه",
            "goolnk.com", "الرصيد", "Vodafone", "Instapay", "للبحرام",
            "الحميل", "RedotPay", "Binance", "Bybit", "السبع", "تحويل من"
        ]
        return any(keyword in message_text for keyword in keywords)
    
    async def process_messages(self):
        """معالجة الرسائل الجديدة"""
        try:
            updates = await self.get_channel_messages()
            
            for update in updates:
                if 'channel_post' in update:
                    message = update['channel_post']
                    message_id = message['message_id']
                    
                    # معالجة الرسائل الجديدة فقط
                    if message_id > self.last_message_id:
                        self.last_message_id = message_id
                        
                        message_text = ""
                        if 'text' in message:
                            message_text = message['text']
                        elif 'caption' in message:
                            message_text = message['caption']
                        
                        if message_text and self.is_sendpulse_message(message_text):
                            logger.info(f"✅ تم العثور على رسالة SendPulse: {message_id}")
                            
                            # إعادة إرسال الرسالة إلى الجروب
                            formatted_message = f"🛒 **طلب SendPulse**\n\n{message_text}\n\n⚡ **تم التوجيه تلقائياً**"
                            
                            await self.bot.send_message(
                                chat_id=TELEGRAM_GROUP_ID,
                                text=formatted_message,
                                reply_markup=self.create_keyboard(),
                                parse_mode='Markdown'
                            )
                            
                            logger.info(f"✅ تم إعادة إرسال الرسالة إلى الجروب")
            
        except Exception as e:
            logger.error(f"❌ خطأ في معالجة الرسائل: {e}")
    
    async def run(self):
        """تشغيل المراقبة"""
        logger.info("🚀 بدء مراقبة قناة SendPulse...")
        
        while True:
            await self.process_messages()
            await asyncio.sleep(10)  # الانتظار 10 ثواني بين كل فحص

async def main():
    """الدالة الرئيسية"""
    if not BOT_TOKEN or not TELEGRAM_GROUP_ID:
        logger.error("❌ متغيرات بيئية مفقودة")
        return
    
    monitor = SendPulseMonitor()
    await monitor.run()

if __name__ == '__main__':
    asyncio.run(main())
