"""Simple Bale echo bot.

Run with: python setup.js
Set BALE_BOT_TOKEN to the token received from Bale's @botfather.
"""

import logging
import os
import threading
import time

import requests
from flask import Flask, jsonify


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


def poll_updates():
    offset = None
    while True:
        try:
            params = {"timeout": 30, "limit": 100}
            if offset is not None:
                params["offset"] = offset
            response = HTTP.get(f"{API_URL}/getUpdates", params=params, timeout=40)
            response.raise_for_status()
            result = response.json()
            if not result.get("ok"):
                raise RuntimeError(result.get("description", "getUpdates failed"))

            for update in result.get("result", []):
                offset = update.get("update_id", 0) + 1
                message = update.get("message")
                if message and not message.get("from", {}).get("is_bot", False):
                    try:
                        echo_message(message)
                    except (requests.RequestException, RuntimeError, ValueError):
                        logger.exception("Could not echo update %s", update.get("update_id"))
        except (requests.RequestException, RuntimeError, ValueError):
            logger.exception("Bale polling failed; retrying in 3 seconds")
            time.sleep(3)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Set the BALE_BOT_TOKEN environment variable before starting the bot.")

    threading.Thread(target=poll_updates, daemon=True, name="bale-polling").start()
    # Flask exposes a lightweight health endpoint; the bot receives updates by long polling.
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), use_reloader=False)
