import logging
from pathlib import Path

from aiohttp import web

from bot.config import get_config
from bot.database.engine import async_session
from bot.services.alpino_service import (
    get_active_user, get_pending_points, get_points_balance, get_points_history, get_rank, resolve_role,
)
from bot.webapp.security import extract_telegram_id, verify_init_data

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


def _auth_or_none(request: web.Request) -> str | None:
    """initData 'Authorization' header yoki 'init_data' query orqali keladi."""
    return request.headers.get("X-Telegram-Init-Data") or request.query.get("init_data")


async def _require_telegram_id(request: web.Request) -> int | None:
    """MUHIM XAVFSIZLIK QOIDASI: har bir /alpino/api/* so'rovda initData
    HMAC orqali tasdiqlanadi - aks holda istalgan kishi o'zini boshqa
    foydalanuvchi sifatida ko'rsatishi mumkin edi."""
    config = get_config()
    raw_init_data = _auth_or_none(request)
    if not raw_init_data:
        return None
    verified = verify_init_data(raw_init_data, config.bot_token)
    if verified is None:
        return None
    return extract_telegram_id(verified)


async def handle_index(request: web.Request) -> web.Response:
    html_path = STATIC_DIR / "alpino_miniapp.html"
    return web.FileResponse(html_path)


async def handle_me(request: web.Request) -> web.Response:
    telegram_id = await _require_telegram_id(request)
    if telegram_id is None:
        return web.json_response({"error": "unauthorized"}, status=401)

    async with async_session() as session:
        user = await get_active_user(session, telegram_id)
        role = resolve_role(user)

        if role != "student":
            return web.json_response({"role": role})

        balance = await get_points_balance(session, user.id)
        rank = await get_rank(session, user.id, balance)
        pending = await get_pending_points(session, user.id)

        return web.json_response({
            "role": "student",
            "full_name": user.full_name,
            "points": balance,
            "rank": rank,
            "pending_count": len(pending),
        })


async def handle_history(request: web.Request) -> web.Response:
    telegram_id = await _require_telegram_id(request)
    if telegram_id is None:
        return web.json_response({"error": "unauthorized"}, status=401)

    async with async_session() as session:
        user = await get_active_user(session, telegram_id)
        if user is None or resolve_role(user) != "student":
            return web.json_response({"error": "forbidden"}, status=403)

        history = await get_points_history(session, user.id)
        return web.json_response({
            "history": [
                {
                    "amount": h.amount,
                    "category": h.category,
                    "status": h.status.value,
                    "reject_reason": h.reject_reason,
                    "created_at": h.created_at.isoformat() if h.created_at else None,
                }
                for h in history
            ]
        })


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/alpino", handle_index)
    app.router.add_get("/alpino/", handle_index)
    app.router.add_get("/alpino/api/me", handle_me)
    app.router.add_get("/alpino/api/history", handle_history)
    return app


async def run_webapp(port: int) -> web.AppRunner:
    """main.py'dan chaqiriladi - botning O'ZI bilan bir xil jarayonda,
    alohida Railway xizmati OCHMASDAN ishga tushadi."""
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Alpino web-server ishga tushdi: 0.0.0.0:{port}")
    return runner
