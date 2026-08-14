import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


def verify_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> dict | None:
    """Telegram WebApp'dan kelgan initData'ni HMAC orqali tasdiqlaydi.

    MUHIM: bu tekshiruv o'tkazib yuborilsa, istalgan kishi o'zini boshqa
    foydalanuvchi (yoki admin) sifatida ko'rsatishi mumkin - shuning uchun
    HAR BIR /alpino/* so'rovida bu funksiya albatta chaqirilishi shart.

    Muvaffaqiyatli bo'lsa - parse qilingan ma'lumotlar lug'atini (jumladan
    'user' -> dict) qaytaradi. Tasdiqlanmasa yoki eskirgan bo'lsa - None.
    """
    try:
        parsed = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        return None

    auth_date = parsed.get("auth_date")
    if auth_date and (time.time() - int(auth_date)) > max_age_seconds:
        return None  # eskirgan sessiya (masalan, ilgari saqlangan link)

    if "user" in parsed:
        try:
            parsed["user"] = json.loads(parsed["user"])
        except (json.JSONDecodeError, TypeError):
            return None

    return parsed


def extract_telegram_id(verified_data: dict) -> int | None:
    user = verified_data.get("user")
    if not isinstance(user, dict):
        return None
    return user.get("id")
