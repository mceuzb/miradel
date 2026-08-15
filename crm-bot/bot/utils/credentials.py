"""O'qituvchi qo'lda qo'shgan (hali Telegram'i bog'lanmagan) o'quvchilar
uchun login/parol generatsiya qilish va parolni xavfsiz saqlash.

Parol shifrlash uchun tashqi kutubxona (bcrypt/passlib) ishlatilmaydi -
requirements.txt'da yo'q, shuning uchun standart kutubxonadagi PBKDF2-HMAC
ishlatiladi (xavfsiz va qo'shimcha dependency talab qilmaydi).
"""

import hashlib
import secrets

# Bu "pepper" - bazaga yozilmaydi, kod ichida qattiq belgilangan. Real
# xavfsizlik parolning o'zi (tasodifiy 6 xonali kod) + PBKDF2 iteratsiyasidan
# keladi, pepper faqat qo'shimcha qatlam.
_PEPPER = "miradel-alpino-login-v1"
_ITERATIONS = 200_000


def generate_login_code() -> str:
    """Masalan: 'ST4821'. Yagonaligini chaqiruvchi tomon (DB orqali) tekshiradi."""
    return f"ST{secrets.randbelow(9000) + 1000}"


def generate_password() -> str:
    """Tasodifiy 6 xonali raqamli parol - o'quvchi/ota-ona uchun eslab qolish oson."""
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", f"{_PEPPER}:{password}".encode(), bytes.fromhex(salt), _ITERATIONS,
    )
    return f"{salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        salt, digest_hex = password_hash.split("$", 1)
    except (ValueError, AttributeError):
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", f"{_PEPPER}:{password}".encode(), bytes.fromhex(salt), _ITERATIONS,
    )
    return secrets.compare_digest(digest.hex(), digest_hex)
