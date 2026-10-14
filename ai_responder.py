"""Send user text to the configured OpenAI-compatible AI service."""

import os
import sys
import json

from openai import OpenAI
from json_data_store import read_data, write_data


BASE_URL = os.environ.get("AI_BASE_URL", "https://api.gapgpt.app/v1").strip()
MODEL = os.environ.get("AI_MODEL", "gpt-6-luna").strip()
API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
FILE_PATH = os.environ.get("FILE_PATH", "").strip()

# Prompt for a key only when run from an interactive terminal. WSGI servers
# should receive the key through the OPENAI_API_KEY environment variable.
if not API_KEY and sys.stdin.isatty():
    API_KEY = input("AI API key: ").strip()


SYSTEM_PROMPT = """You are an assistant that answers the user and may edit one JSON data file.
Return exactly one valid JSON object with exactly these keys:
{"answer": "reply to the user", "datas": null}

The current file contents will be provided as JSON in the user message.
Change the data only when the user's explicit request asks for a change to it.
Make only the changes the user specifically requested. Never make extra,
unsolicited, inferred, or self-directed changes. If the user did not request a
file change, set datas to null. If the user requested a change, put the complete
updated JSON file value in datas. Keep answer as a normal, concise response for
the user. Do not put markdown fences or any text outside the JSON object."""


def get_ai_reply(user_text: str) -> str:
    """Ask the AI, apply an explicitly requested JSON edit, and return answer."""
    if not API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    if not FILE_PATH:
        raise RuntimeError("FILE_PATH is not configured")

    current_data = read_data(FILE_PATH)

    client = OpenAI(base_url=BASE_URL, api_key=API_KEY)
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {"message": user_text, "current_datas": current_data},
                    ensure_ascii=False,
                ),
            },
        ],
    )
    raw_result = (response.choices[0].message.content or "").strip()
    result = json.loads(raw_result)
    if not isinstance(result, dict) or not isinstance(result.get("answer"), str):
        raise ValueError("AI response must be a JSON object with a string answer")
    if "datas" not in result:
        raise ValueError("AI response is missing the datas field")

    if result["datas"] is not None:
        write_data(FILE_PATH, result["datas"])

    return result["answer"]
