"""Alpino Mini App uchun aiohttp web-server.

MUHIM: bu funksiya HECH QACHON to'g'ridan-to'g'ri `await` qilinmasin
(masalan `await run_webapp(port)` ko'rinishida) - u ichida
`site.start()` chaqirilgach ham server abadiy ishlab turadi, lekin
funksiyaning o'zi darhol qaytadi (blocking emas). Botning asosiy
polling siklidan oldin emas, unga PARALLEL background task sifatida
ishga tushirilishi kerak - main.py'da `asyncio.create_task(run_webapp(...))`
orqali.

Hozircha faqat health-check endpoint bor. Alpino API endpoint'lari
(TZ v3, 5-bo'lim) shu yerga, alohida router fayllar sifatida
qo'shib boriladi (masalan bot/webapp/alpino_routes.py).
"""

import logging

from aiohttp import web

logger = logging.getLogger(__name__)


async def health_check(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/health", health_check)
    # TODO (Alpino TZ v3, 5-bo'lim): bu yerga /alpino/* endpoint'lari qo'shiladi
    return app


async def run_webapp(port: int) -> None:
    """Serverni fon vazifasi (background task) sifatida ishga tushiradi.
    Bloklamaydi - darhol qaytadi, server orqa fonda ishlab turadi."""
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    logger.info(f"Alpino webapp {port}-portda ishga tushdi (health-check faol)")
