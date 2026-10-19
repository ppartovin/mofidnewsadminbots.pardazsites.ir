"""Send user text to the configured OpenAI-compatible AI service."""

import os
import sys
import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import jdatetime
from openai import OpenAI, OpenAIError
from bot_logging import get_logger
from error_handling import AIResponseError, AIServiceError, ConfigError, parse_ai_result
from json_data_store import read_data, read_school_schedule, write_data

logger = get_logger("ai")


BASE_URL = os.environ.get("AI_BASE_URL", "https://api.gapgpt.app/v1").strip()
MODEL = os.environ.get("AI_MODEL", "gpt-6-luna").strip()
API_KEY = os.environ.get("AI_API_KEY", "").strip()
FILE_PATH = os.environ.get("FILE_PATH", "").strip()

# Prompt for a key only when run from an interactive terminal. WSGI servers
# should receive the key through the OPENAI_API_KEY environment variable.
if not API_KEY and sys.stdin.isatty():
    API_KEY = input("AI API key: ").strip()


SYSTEM_PROMPT = """You are an assistant that answers the user and may edit one JSON data file.
Return exactly one valid JSON object with exactly these keys:
{"answer": "reply to the user", "datas": null}

The current contents of the configurable data file and the read-only school
schedule will be provided as JSON in the user message. Use the school schedule
as context when answering. Only the configurable data file may be changed;
never change the school schedule.
Change the data only when the user's explicit request asks for a change to it.
Make only the changes the user specifically requested. Never make extra,
unsolicited, inferred, or self-directed changes. If the user did not request a
file change, set datas to null. If the user requested a change, put the complete
updated JSON file value in datas. Keep answer as a normal, concise response for
the user. Do not put markdown fences or any text outside the JSON object."""


def get_ai_reply(user_text: str) -> str:
    """Ask the AI, apply an explicitly requested JSON edit, and return answer."""
    if not API_KEY:
        logger.error("AI_API_KEY is not configured")
        raise ConfigError("AI_API_KEY is not configured")
    if not FILE_PATH:
        logger.error("FILE_PATH is not configured")
        raise ConfigError("FILE_PATH is not configured")

    current_data = read_data(FILE_PATH)
    school_schedule = read_school_schedule()
    tehran_now = datetime.now(ZoneInfo("Asia/Tehran"))
    today_jalali = jdatetime.datetime.fromgregorian(datetime=tehran_now).strftime(
        "%Y/%m/%d"
    )

    logger.info("AI request | model=%s base_url=%s today_jalali=%s", MODEL, BASE_URL, today_jalali)
    started = time.monotonic()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "message": user_text,
                    "current_datas": current_data,
                    "school_schedule": school_schedule,
                    "today_jalali": today_jalali,
                },
                ensure_ascii=False,
            ),
        },
    ]
    logger.info(
        "AI input | model=%s today_jalali=%s user_text=%s",
        MODEL,
        today_jalali,
        user_text,
    )
    try:
        with OpenAI(base_url=BASE_URL, api_key=API_KEY) as client:
            response = client.chat.completions.create(model=MODEL, messages=messages)
    except OpenAIError as error:
        logger.exception("AI request failed | error=%s", type(error).__name__)
        raise AIServiceError(f"AI request failed: {type(error).__name__}") from error
    if not getattr(response, "choices", None):
        logger.error("AI response has no choices | id=%s", getattr(response, "id", None))
        raise AIResponseError("AI response contained no choices")
    logger.info(
        "AI response received | duration_ms=%d usage=%s",
        (time.monotonic() - started) * 1000,
        getattr(response, "usage", None),
    )
    raw_result = (response.choices[0].message.content or "").strip()
    logger.info(
        "AI full output | id=%s model=%s finish_reason=%s raw=%s",
        getattr(response, "id", None),
        getattr(response, "model", None),
        response.choices[0].finish_reason,
        raw_result,
    )
    try:
        result = parse_ai_result(raw_result)
    except AIResponseError as error:
        logger.error("AI response rejected | error=%s raw=%.500s", error, raw_result)
        raise

    if result["datas"] is not None:
        logger.info("AI requested data file update | path=%s", FILE_PATH)
        write_data(FILE_PATH, result["datas"])
    else:
        logger.info("AI made no data changes")

    return result["answer"]
