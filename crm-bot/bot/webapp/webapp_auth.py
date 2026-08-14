"""Telegram WebApp `initData`ni tasdiqlash (TZ v3, 4.2-band).

Rasmiy algoritm:
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app

Bu tekshiruv MAJBURIY - aks holda istalgan kishi brauzer konsolida
o'zini boshqa telegram_id sifatida ko'rsatishi (soxtalashtirish) mumkin.
"""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


def verify_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> dict | None:
    """Muvaffaqiyatli bo'lsa parslangan dict qaytaradi: {"user": {...}, "auth_date": int, ...}
    Muvaffaqiyatsiz (soxta yoki eskirgan) bo'lsa - None."""
    try:
        pairs = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))

    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        return None

    auth_date = pairs.get("auth_date")
    if auth_date is None:
        return None
    try:
        auth_date_int = int(auth_date)
    except ValueError:
        return None
    if time.time() - auth_date_int > max_age_seconds:
        return None  # replay hujumidan himoya - eskirgan initData

    result = dict(pairs)
    if "user" in result:
        try:
            result["user"] = json.loads(result["user"])
        except json.JSONDecodeError:
            return None
    result["auth_date"] = auth_date_int
    return result
