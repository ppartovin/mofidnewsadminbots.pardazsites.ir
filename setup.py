
import os
from flask import Flask, request
from ai_responder import get_ai_reply
import time
from bot_logging import get_logger, new_request_id
from error_handling import (
    BaleAPIError,
    as_dict,
    as_text,
    bale_request,
    fit_bale_text,
    user_message_for,
)

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
        if not isinstance(update, dict):
            logger.warning("Webhook body is not a valid JSON object")
            update = {}
        message = as_dict(update.get("message"))
        chat_id = as_dict(message.get("chat")).get("id")
        logger.debug("Update parsed | update_id=%s keys=%s", update.get("update_id"), list(update))

        if not TOKEN:
            logger.error("BALE_BOT_TOKEN is empty")
            return "Token is missing", 500

        if chat_id is None:
            logger.info("Ignored update without chat id | update_id=%s", update.get("update_id"))
            return "ok", 200

        user_text = as_text(message.get("text")) or as_text(message.get("caption"))
        if not user_text:
            logger.info("Non-text message | chat_id=%s", chat_id)
            reply = "فعلاً فقط پیام‌های متنی را می‌توانم پاسخ بدهم."
            try:
                bale_request(API_URL, "sendMessage", {"chat_id": chat_id, "text": reply})
            except BaleAPIError as error:
                logger.error("Unsupported-message reply failed | chat_id=%s error=%s", chat_id, error)
            return "ok", 200

        logger.info("User message | chat_id=%s chars=%s", chat_id, len(user_text))
        logger.debug("User message text | chat_id=%s text=%r", chat_id, user_text[:500])
        try:
            sent_result = bale_request(
                API_URL, "sendMessage", {"chat_id": chat_id, "text": "در حال پردازش..."}
            )
        except BaleAPIError as error:
            logger.error("Status message failed | chat_id=%s error=%s", chat_id, error)
            return "ok", 200
        status_message_id = as_dict(sent_result.get("result")).get("message_id")
        if status_message_id is None:
            logger.error("Bale response did not include status message_id | chat_id=%s", chat_id)
            return "ok", 200

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
            reply = user_message_for(error)

        try:
            bale_request(
                API_URL,
                "editMessageText",
                {
                    "chat_id": chat_id,
                    "message_id": status_message_id,
                    "text": fit_bale_text(reply),
                },
            )
            logger.info(
                "Bale edit done | chat_id=%s total_ms=%d",
                chat_id,
                (time.monotonic() - started) * 1000,
            )
        except BaleAPIError as error:
            logger.error("Bale edit failed | chat_id=%s error=%s", chat_id, error)
        return "ok", 200

    except Exception:
        logger.exception(
            "Unhandled webhook error | request_id=%s total_ms=%d",
            request_id,
            (time.monotonic() - started) * 1000,
        )
        exit(1)
        return "ok", 200


@app.route("/", methods=["GET"])
def home():
    logger.info("Health check | remote=%s", request.remote_addr)
    return "Bot is running", 200



