import os
import logging
import json
from flask import Flask, request, jsonify
import requests
from requests.adapters import HTTPAdapter, Retry

# ---------------------------
# إعداد اللوج
# ---------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------
# إعداد Flask
# ---------------------------
app = Flask(__name__)

# ---------------------------
# قراءة المتغيرات البيئية
# ---------------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("GROUP_ID")
# اختياري: تعرّف 6 عناوين أزرار مفصولة بفاصلة (مثال: "قبول,رفض,تحقق,...")
BUTTON_LABELS = os.getenv("BUTTON_LABELS")  # example: "قبول,رفض,تحقق,دفع,اتصال,صورة"
# اختياري: تحدد أفعال الأزرار مفصولة بفاصلة. إذا بدأ العنصر بـ "http" سيصبح زر URL، وإلا فيكون callback_data
# مثال: "accept,decline,check,http://example.com/pay,call,photo"
BUTTON_ACTIONS = os.getenv("BUTTON_ACTIONS")

# ---------------------------
# HTTP session مع retries
# ---------------------------
session = requests.Session()
retries = Retry(total=3, backoff_factor=0.5, status_forcelist=(500, 502, 504))
session.mount("https://", HTTPAdapter(max_retries=retries))

# ---------------------------
# Helpers
# ---------------------------
def safe_chat_id(val):
    if val is None:
        return None
    try:
        # chat ids in Telegram can be negative (groups)
        return int(val)
    except Exception:
        return val  # return as-is if not numeric


def build_reply_markup(labels: str = None, actions: str = None):
    """بناء reply_markup بشكل مرن. يعيد dict جاهز للـ Bot API."""
    default_labels = ["زر 1", "زر 2", "زر 3", "زر 4", "زر 5", "زر 6"]
    default_actions = ["btn1", "btn2", "btn3", "btn4", "btn5", "btn6"]

    if labels:
        parts = [p.strip() for p in labels.split(",")]
        # fill or cut to 6
        labels_list = (parts + default_labels)[:6]
    else:
        labels_list = default_labels

    if actions:
        parts = [p.strip() for p in actions.split(",")]
        actions_list = (parts + default_actions)[:6]
    else:
        actions_list = default_actions

    # arrange into rows of 2 buttons each (3 صفوف × 2 أزرار)
    keyboard = []
    for i in range(0, 6, 2):
        row = []
        for j in (0, 1):
            idx = i + j
            label = labels_list[idx]
            act = actions_list[idx]

            if act.lower().startswith("http://") or act.lower().startswith("https://"):
                btn = {"text": label, "url": act}
            else:
                btn = {"text": label, "callback_data": act}
            row.append(btn)
        keyboard.append(row)

    return {"inline_keyboard": keyboard}


def telegram_api(method: str, payload: dict):
    """نداء عام إلى Telegram Bot API باستخدام requests."""
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN غير محدد في المتغيرات البيئية.")

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    resp = session.post(url, json=payload, timeout=10)
    try:
        j = resp.json()
    except Exception:
        log.error("Telegram response not JSON: %s", resp.text)
        resp.raise_for_status()
    if not j.get("ok"):
        log.error("Telegram API returned error: %s", j)
    return j


# ---------------------------
# Route: استقبال POST من SendPulse
# ---------------------------
@app.route("/sendpulse", methods=["POST"])
def handle_sendpulse():
    """نقطة دخول من SendPulse Flow (POST)."""
    try:
        data = request.get_json(force=True, silent=True)
        if data is None:
            # لو body مش JSON، خد raw text
            raw = request.get_data(as_text=True)
            log.info("Received non-JSON body from SendPulse: %s", raw)
            data = {"raw": raw}

        log.info("📩 Data received from SendPulse: %s", data)

        # نحاول نقرأ الحقول الشائعة (لو متوفرة)
        name = data.get("name") or data.get("client_name") or data.get("username")
        user_id = data.get("id") or data.get("user_id")
        amount = data.get("amount")
        payment = data.get("payment")

        # رسالة قابلة للتكيف: لو الحقول موجودة نعرضها، وإلا نعرض ال JSON كامل
        if any([name, user_id, amount, payment]):
            message_lines = ["📩 إشعار جديد من SendPulse:\n"]
            if name:
                message_lines.append(f"👤 الاسم: {name}")
            if user_id:
                message_lines.append(f"🆔 ID: {user_id}")
            if amount:
                message_lines.append(f"💵 المبلغ: {amount}")
            if payment:
                message_lines.append(f"💳 طريقة الدفع: {payment}")
            # أي حقول إضافية نلحقها تحت
            extra = {k: v for k, v in data.items() if k not in ("name", "client_name", "username", "id", "user_id", "amount", "payment")}
            if extra:
                message_lines.append("\n🔎 بيانات إضافية:")
                message_lines.append(json.dumps(extra, ensure_ascii=False, indent=2))
            message_text = "\n".join(message_lines)
        else:
            # لو مفيش حقول مفهومة نبعث الـ JSON كامل (مقطع ومقروء)
            pretty = json.dumps(data, ensure_ascii=False, indent=2)
            message_text = f"📩 إشعار جديد (raw payload):\n\n{pretty}"

        # بناء الأزرار (من env أو الافتراضي)
        reply_markup = build_reply_markup(BUTTON_LABELS, BUTTON_ACTIONS)

        # إرسال الرسالة للتليجرام
        chat_id = safe_chat_id(TELEGRAM_CHAT_ID)
        if not chat_id:
            log.error("TELEGRAM_CHAT_ID غير مُعرَّف. فضلاً حدده كمتغير بيئي.")
            return jsonify({"status": "error", "message": "TELEGRAM_CHAT_ID not set"}), 500

        payload = {
            "chat_id": chat_id,
            "text": message_text,
            "parse_mode": "HTML",
            "reply_markup": reply_markup,
            "disable_web_page_preview": True,
        }

        resp = telegram_api("sendMessage", payload)
        log.info("✅ Sent to Telegram: %s", resp)
        return jsonify({"status": "ok", "telegram_result": resp})
    except Exception as e:
        log.exception("❌ Error handling SendPulse webhook:")
        return jsonify({"status": "error", "message": str(e)}), 500


# ---------------------------
# Route: نقطة استقبال Webhook من Telegram (اختياري)
# ---------------------------
@app.route("/telegram-webhook", methods=["POST"])
def telegram_webhook():
    """
    يستقبل تحديثات من Telegram لو ضبطت webhook للبوت. 
    الآن نعالج callback_query البسيط ونرد answerCallbackQuery.
    """
    try:
        update = request.get_json(force=True, silent=True) or {}
        log.info("🔔 Telegram update: %s", update)

        # معالجة callback_query
        cb = update.get("callback_query")
        if cb:
            callback_id = cb.get("id")
            data = cb.get("data")
            from_user = cb.get("from", {})
            user_name = from_user.get("username") or from_user.get("first_name")
            message_id = cb.get("message", {}).get("message_id")
            chat = cb.get("message", {}).get("chat", {})
            chat_id = chat.get("id")

            # نرد على callback داخل الواجهة (نغلق الدائرة)
            telegram_api("answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": f"تم الضغط: {data}",
                "show_alert": False,
            })

            # نرسل رسالة صغيرة في نفس الجروب تُفيد بالاختيار (اختياري)
            text = f"🖱️ @{user_name or 'مستخدم'} اختار: {data}"
            telegram_api("sendMessage", {"chat_id": chat_id, "text": text})

            return jsonify({"status": "ok", "handled": "callback_query"})

        # لو تحديثات تانية، بس نلّوجها
        return jsonify({"status": "ok", "received_update": update})
    except Exception as e:
        log.exception("Error in telegram_webhook")
        return jsonify({"status": "error", "message": str(e)}), 500


# ---------------------------
# Health
# ---------------------------
@app.route("/", methods=["GET"])
def home():
    return "✅ Bot relay is running."


# ---------------------------
# Run (development)
# ---------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT") or 8000)
    host = "0.0.0.0"
    log.info("Starting app on %s:%s", host, port)
    app.run(host=host, port=port)
