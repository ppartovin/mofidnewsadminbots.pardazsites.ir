
import os
import requests
from flask import Flask, request
from ai_responder import get_ai_reply
import time
from bot_logging import get_logger, new_request_id

app = Flask(__name__)
logger = get_logger("webhook")

 
TOKEN = os.environ.get("BALE_BOT_TOKEN", "").strip()
API_URL = f"https://tapi.bale.ai/bot{TOKEN}"
if not TOKEN:
    logger.error("BALE_BOT_TOKEN is not configured")
logger.info("App initialised | ai_key_set=%s", bool(os.environ.get("AI_API_KEY", "").strip()))


@app.route("/webhook", methods=["POST"])
def webhook():
    request_id = new_request_id()
    started = time.monotonic()
    logger.info(
        "Webhook received | remote=%s bytes=%s",
        request.headers.get("X-Forwarded-For", request.remote_addr),
        request.content_length,
    )
    try:
        update = request.get_json(silent=True)
        if update is None:
            logger.warning("Webhook body is not valid JSON")
            update = {}
        message = update.get("message") or {}
        chat_id = (message.get("chat") or {}).get("id")
        logger.debug("Update parsed | update_id=%s keys=%s", update.get("update_id"), list(update))

        if not TOKEN:
            logger.error("BALE_BOT_TOKEN is empty")
            return "Token is missing", 500

        if chat_id is None:
            logger.info("Ignored update without chat id | update_id=%s", update.get("update_id"))
            return "ok", 200

        user_text = (message.get("text") or message.get("caption") or "").strip()
        if not user_text:
            logger.info("Non-text message | chat_id=%s", chat_id)
            reply = "فعلاً فقط پیام‌های متنی را می‌توانم پاسخ بدهم."
            unsupported = requests.post(
                f"{API_URL}/sendMessage",
                json={"chat_id": chat_id, "text": reply},
                timeout=20,
            )
            logger.info("Unsupported-message reply sent | chat_id=%s status=%s", chat_id, unsupported.status_code)
            return "ok", 200

        logger.info("User message | chat_id=%s chars=%s", chat_id, len(user_text))
        logger.debug("User message text | chat_id=%s text=%r", chat_id, user_text[:500])
        sent = requests.post(
            f"{API_URL}/sendMessage",
            json={"chat_id": chat_id, "text": "در حال پردازش..."},
            timeout=20,
        )
        logger.info("Bale status message | status=%s body=%s", sent.status_code, sent.text)
        sent.raise_for_status()
        sent_result = sent.json()
        status_message_id = (sent_result.get("result") or {}).get("message_id")
        if status_message_id is None:
            raise RuntimeError("Bale response did not include status message_id")

        ai_started = time.monotonic()
        try:
            reply = get_ai_reply(user_text)
            if not reply:
                logger.warning("AI returned an empty reply | chat_id=%s", chat_id)
                reply = "پاسخی دریافت نشد. لطفاً دوباره تلاش کنید."
            logger.info(
                "AI reply ready | chat_id=%s chars=%s duration_ms=%d",
                chat_id,
                len(reply),
                (time.monotonic() - ai_started) * 1000,
            )
        except Exception as error:
            logger.exception(
                "AI failure | chat_id=%s error=%s duration_ms=%d",
                chat_id,
                type(error).__name__,
                (time.monotonic() - ai_started) * 1000,
            )
            reply = "در دریافت پاسخ از هوش مصنوعی خطایی رخ داد. لطفاً بعداً تلاش کنید."

        response = requests.post(
            f"{API_URL}/editMessageText",
            json={"chat_id": chat_id, "message_id": status_message_id, "text": reply},
            timeout=20,
        )

        level = logger.info if response.ok else logger.error
        level(
            "Bale edit response | chat_id=%s status=%s body=%s total_ms=%d",
            chat_id,
            response.status_code,
            response.text,
            (time.monotonic() - started) * 1000,
        )
        return "ok", 200

    except Exception:
        logger.exception(
            "Unhandled webhook error | request_id=%s total_ms=%d",
            request_id,
            (time.monotonic() - started) * 1000,
        )
        return "error", 500


@app.route("/", methods=["GET"])
def home():
    logger.info("Health check | remote=%s", request.remote_addr)
    return "Bot is running", 200



