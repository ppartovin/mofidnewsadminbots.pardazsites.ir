"""Simple Bale echo bot.

Run with: a WSGI server (for example, Passenger via passenger_wsgi.py).
Set BALE_BOT_TOKEN to the token received from Bale's @botfather.
"""

import logging
import os
import requests
from flask import Flask, jsonify, request


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)
app = Flask(__name__)

TOKEN = os.getenv("BALE_BOT_TOKEN", "").strip()
API_URL = f"https://tapi.bale.ai/bot{TOKEN}"
HTTP = requests.Session()


@app.get("/")
def health_check():
    return jsonify(status="ok", bot="bale-echo")


def call_bale(method, **payload):
    response = HTTP.post(f"{API_URL}/{method}", json=payload, timeout=40)
    response.raise_for_status()
    result = response.json()
    if not result.get("ok"):
        raise RuntimeError(result.get("description", f"Bale API error: {method}"))
    return result.get("result")


def echo_message(message):
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    message_id = message.get("message_id")
    if chat_id is None or message_id is None:
        return

    # copyMessage echoes text and supported media without downloading/re-uploading it.
    call_bale("copyMessage", chat_id=chat_id, from_chat_id=chat_id, message_id=message_id)


@app.post("/webhook")
def receive_update():
    update = request.get_json(silent=True)
    if not isinstance(update, dict):
        return jsonify(ok=False, error="Expected a JSON update"), 400

    message = update.get("message")
    if message and not message.get("from", {}).get("is_bot", False):
        try:
            echo_message(message)
        except (requests.RequestException, RuntimeError, ValueError):
            logger.exception("Could not echo update %s", update.get("update_id"))
            return jsonify(ok=False), 500

    return jsonify(ok=True)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Set the BALE_BOT_TOKEN environment variable before starting the bot.")

    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), use_reloader=False)
