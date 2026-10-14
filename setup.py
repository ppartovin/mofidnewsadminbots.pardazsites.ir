
import os
import requests
from flask import Flask, request

app = Flask(__name__)


def log(text):
    with open(os.path.join(os.path.dirname(__file__), "bot.log"), "a", encoding="utf-8") as f:
        f.write(str(text) + "\n")


TOKEN = os.environ.get("BALE_BOT_TOKEN", "").strip()
API_URL = f"https://tapi.bale.ai/bot{TOKEN}"


@app.route("/webhook", methods=["POST"])
def webhook():
    log("Webhook received")
    log(request.get_data(as_text=True))

    try:
        update = request.get_json(silent=True) or {}
        message = update.get("message") or {}
        chat_id = (message.get("chat") or {}).get("id")
        message_id = message.get("message_id")

        if not TOKEN:
            log("ERROR: BALE_BOT_TOKEN is empty")
            return "Token is missing", 500

        if chat_id is None or message_id is None:
            log("No message to copy")
            return "ok", 200

        response = requests.post(
            f"{API_URL}/copyMessage",
            json={
                "chat_id": chat_id,
                "from_chat_id": chat_id,
                "message_id": message_id,
            },
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