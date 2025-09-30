import os
import requests
from flask import Flask, request
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import telebot
import uuid
import json

# --- المتغيرات ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SENDPULSE_API_URL = os.getenv("SENDPULSE_API_URL")
SENDPULSE_TOKEN = os.getenv("SENDPULSE_TOKEN")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON", "credentials.json")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
app = Flask(__name__)

# --- Google Drive API ---
SCOPES = ['https://www.googleapis.com/auth/drive.file']
creds = service_account.Credentials.from_service_account_file(GOOGLE_CREDENTIALS_JSON, scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=creds)

# تخزين حالة انتظار صورة
waiting_for_image = {}  # {chat_id: contact_id}

# --- إرسال رسالة للعميل عبر SendPulse ---
def send_to_client(contact_id, image_url=None, text="تم تنفيذ طلبك بنجاح ✅"):
    headers = {"Authorization": f"Bearer {SENDPULSE_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "contact_id": contact_id,
        "message": {"text": text}
    }
    if image_url:
        payload["message"]["image"] = image_url
    requests.post(SENDPULSE_API_URL, json=payload, headers=headers)

# --- رفع صورة لـ Google Drive ---
def upload_to_drive(file_path):
    file_metadata = {'name': f"{uuid.uuid4()}.jpg"}
    media = MediaFileUpload(file_path, mimetype='image/jpeg')
    file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    drive_service.permissions().create(fileId=file['id'], body={'role': 'reader', 'type': 'anyone'}).execute()
    return f"https://drive.google.com/uc?id={file['id']}"

# --- زر تنفيذ الطلب ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("execute_order:"))
def execute_order(call):
    contact_id = call.data.split(":")[1]
    bot.delete_message(call.message.chat.id, call.message.message_id)
    send_to_client(contact_id)
    bot.answer_callback_query(call.id, "✅ تم تنفيذ الطلب")

# --- زر إرسال صورة ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("send_image:"))
def send_image(call):
    contact_id = call.data.split(":")[1]
    waiting_for_image[call.message.chat.id] = contact_id
    bot.send_message(call.message.chat.id, "📷 من فضلك أرسل صورة الآن")
    bot.answer_callback_query(call.id)

# --- استقبال الصور ---
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    if message.chat.id in waiting_for_image:
        contact_id = waiting_for_image[message.chat.id]

        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        temp_file = f"/tmp/{uuid.uuid4()}.jpg"
        with open(temp_file, 'wb') as f:
            f.write(downloaded_file)
        
        # رفع الصورة
        image_url = upload_to_drive(temp_file)
        
        # إرسالها للعميل
        send_to_client(contact_id, image_url=image_url)
        
        # حذف الرسالة من الجروب
        bot.delete_message(message.chat.id, message.message_id)
        
        # إلغاء حالة الانتظار
        del waiting_for_image[message.chat.id]

# --- Flask Webhook ---
@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def telegram_webhook():
    update = request.get_data().decode("utf-8")
    bot.process_new_updates([telebot.types.Update.de_json(update)])
    return "OK", 200

@app.route("/")
def home():
    return "Bot is running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
