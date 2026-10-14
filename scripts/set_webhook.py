"""Register this bot's webhook with Bale.

Usage: python scripts/set_webhook.py https://your-site.example BALE_BOT_TOKEN
The site URL may include a path; /webhook is appended to it.
"""

import sys
from urllib.parse import urlsplit, urlunsplit

import requests

API_BASE = "https://tapi.bale.ai/bot"


def webhook_url(site_url: str) -> str:
    parts = urlsplit(site_url)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("site URL must be an absolute http(s) URL")
    path = parts.path.rstrip("/")
    if not path.endswith("/webhook"):
        path += "/webhook"
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python scripts/set_webhook.py <site-url> <bale-token>", file=sys.stderr)
        return 2

    site_url, token = sys.argv[1].strip(), sys.argv[2].strip()
    if not token:
        print("Bale token cannot be empty.", file=sys.stderr)
        return 2

    try:
        target = webhook_url(site_url)
        response = requests.post(
            f"{API_BASE}{token}/setWebhook",
            json={"url": target},
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()
        if not result.get("ok"):
            raise RuntimeError(result.get("description", "Bale rejected the webhook"))
    except (ValueError, requests.RequestException, RuntimeError) as exc:
        print(f"Could not set Bale webhook: {exc}", file=sys.stderr)
        return 1

    print(f"Webhook set to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
