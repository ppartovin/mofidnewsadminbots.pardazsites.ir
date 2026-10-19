"""Shared error types and helpers used by the webhook, AI and Bale layers."""

import json
import re

import requests

from bot_logging import get_logger

logger = get_logger("errors")

DEFAULT_USER_MESSAGE = "در دریافت پاسخ از هوش مصنوعی خطایی رخ داد. لطفاً بعداً تلاش کنید."
BALE_REQUEST_TIMEOUT = 20
BALE_MAX_TEXT_CHARS = 4096

_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL | re.IGNORECASE)


class BotError(Exception):
    """Base class for expected errors that carry a message safe to show users."""

    user_message = DEFAULT_USER_MESSAGE


class ConfigError(BotError):
    """A required setting is missing or invalid."""

    user_message = "ربات هنوز به‌درستی پیکربندی نشده است. لطفاً به مدیر اطلاع دهید."


class AIServiceError(BotError):
    """The AI service could not be reached or returned an API error."""

    user_message = "سرویس هوش مصنوعی در دسترس نیست. لطفاً کمی بعد دوباره تلاش کنید."


class AIResponseError(BotError):
    """The AI answered, but not in the required format."""

    user_message = "پاسخ هوش مصنوعی نامعتبر بود. لطفاً دوباره تلاش کنید."


class DataFileError(BotError):
    """The JSON data file could not be read or updated."""

    user_message = "خواندن یا ذخیره‌ی اطلاعات با مشکل مواجه شد. لطفاً به مدیر اطلاع دهید."


class BaleAPIError(Exception):
    """A Bale API call failed (network error, HTTP error or ok=false)."""


def user_message_for(error: BaseException) -> str:
    """Return the text that is safe to show the user for this error."""
    if isinstance(error, BotError):
        return error.user_message
    return DEFAULT_USER_MESSAGE


def as_dict(value) -> dict:
    """Return value when it is a dict, otherwise an empty dict."""
    return value if isinstance(value, dict) else {}


def as_text(value) -> str:
    """Return value stripped when it is a string, otherwise an empty string."""
    return value.strip() if isinstance(value, str) else ""


def parse_ai_result(raw_result: str) -> dict:
    """Parse and validate the AI output; raise AIResponseError if unusable."""
    text = (raw_result or "").strip()
    if not text:
        raise AIResponseError("AI returned an empty response")
    fenced = _FENCE_PATTERN.match(text)
    if fenced:
        text = fenced.group(1)
    try:
        result = json.loads(text)
    except json.JSONDecodeError as error:
        raise AIResponseError(f"AI returned invalid JSON: {error}") from error
    if not isinstance(result, dict) or not isinstance(result.get("answer"), str):
        raise AIResponseError("AI response must be a JSON object with a string answer")
    if "datas" not in result:
        raise AIResponseError("AI response is missing the datas field")
    return result


def fit_bale_text(text: str) -> str:
    """Trim text to the Bale message size limit."""
    if len(text) <= BALE_MAX_TEXT_CHARS:
        return text
    return text[: BALE_MAX_TEXT_CHARS - 1] + "…"


def bale_request(api_url: str, method: str, payload: dict) -> dict:
    """Call a Bale API method and return its JSON body or raise BaleAPIError."""
    try:
        response = requests.post(
            f"{api_url}/{method}", json=payload, timeout=BALE_REQUEST_TIMEOUT
        )
    except requests.RequestException as error:
        raise BaleAPIError(f"{method} request failed: {type(error).__name__}") from error

    logger.info(
        "Bale %s response | status=%s body=%.500s",
        method,
        response.status_code,
        response.text,
    )
    if not response.ok:
        raise BaleAPIError(f"{method} returned HTTP {response.status_code}")
    try:
        body = response.json()
    except ValueError as error:
        raise BaleAPIError(f"{method} returned a non-JSON body") from error
    if not isinstance(body, dict) or body.get("ok") is False:
        raise BaleAPIError(f"{method} was rejected by Bale")
    return body
