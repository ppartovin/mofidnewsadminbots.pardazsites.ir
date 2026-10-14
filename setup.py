
import os
import requests
from flask import Flask, request
from ai_responder import get_ai_reply

app = Flask(__name__)


def log(text):
    with open(os.path.join(os.path.dirname(__file__), "bot.log"), "a", encoding="utf-8") as f:
        f.write(str(text) + "\n")


TOKEN = os.environ.get("BALE_BOT_TOKEN", "").strip()
API_URL = f"https://tapi.bale.ai/bot{TOKEN}"


@app.route("/webhook", methods=["POST"])
def webhook():
    log("Webhook received")
    try:
        update = request.get_json(silent=True) or {}
        message = update.get("message") or {}
        chat_id = (message.get("chat") or {}).get("id")

        if not TOKEN:
            log("ERROR: BALE_BOT_TOKEN is empty")
            return "Token is missing", 500

        if chat_id is None:
            log("Message has no chat id")
            return "ok", 200

        user_text = (message.get("text") or message.get("caption") or "").strip()
        if not user_text:
            reply = "فعلاً فقط پیام‌های متنی را می‌توانم پاسخ بدهم."
        else:
            try:
                reply = get_ai_reply(user_text)
                if not reply:
                    reply = "پاسخی دریافت نشد. لطفاً دوباره تلاش کنید."
            except Exception as error:
                log(f"AI ERROR: {type(error).__name__}: {error}")
                reply = "در دریافت پاسخ از هوش مصنوعی خطایی رخ داد. لطفاً بعداً تلاش کنید."

        response = requests.post(
            f"{API_URL}/sendMessage",
            json={"chat_id": chat_id, "text": reply},
            timeout=20,
        )

        log(f"Bale response: {response.status_code} {response.text}")
        return "ok", 200

    except Exception as error:
        log(f"ERROR: {error}")
        return "error", 500


@app.route("/", methods=["GET"])
def home():
    log("app started")
    return "Bot is running", 200
