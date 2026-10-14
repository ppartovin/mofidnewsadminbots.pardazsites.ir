"""Send user text to the configured OpenAI-compatible AI service."""

import os
import sys

from openai import OpenAI


BASE_URL = os.environ.get("AI_BASE_URL", "https://api.gapgpt.app/v1").strip()
MODEL = os.environ.get("AI_MODEL", "gpt-6-luna").strip()
API_KEY = os.environ.get("َAI_API_KEY", "").strip()

# Prompt for a key only when run from an interactive terminal. WSGI servers
# should receive the key through the OPENAI_API_KEY environment variable.
if not API_KEY and sys.stdin.isatty():
    API_KEY = input("AI API key: ").strip()


def get_ai_reply(user_text: str) -> str:
    """Return the AI response for a user's text."""
    if not API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    client = OpenAI(base_url=BASE_URL, api_key=API_KEY)
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": user_text}],
    )
    return (response.choices[0].message.content or "").strip()
