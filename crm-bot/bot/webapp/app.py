"""Alpino Mini App uchun aiohttp web-server.

MUHIM: bu funksiya HECH QACHON to'g'ridan-to'g'ri `await` qilinmasin
(masalan `await run_webapp(port)` ko'rinishida) - u ichida
`site.start()` chaqirilgach ham server abadiy ishlab turadi, lekin
funksiyaning o'zi darhol qaytadi (blocking emas). Botning asosiy
polling siklidan oldin emas, unga PARALLEL background task sifatida
ishga tushirilishi kerak - main.py'da `asyncio.create_task(run_webapp(...))`
orqali.
"""

import logging
import pathlib

from aiohttp import web

logger = logging.getLogger(__name__)

# bot/webapp/static/alpino_miniapp.html shu yerdan o'qiladi
STATIC_DIR = pathlib.Path(__file__).parent / "static"


async def health_check(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def serve_alpino(request: web.Request) -> web.Response:
    """Mini App'ning asosiy HTML sahifasi.
    Hozircha STATIK - ichidagi `state` obyekti hali mock ma'lumotlar bilan
    ishlaydi (TZ v3, 5-6-bo'limlarda backend'ga ulanguncha)."""
    file_path = STATIC_DIR / "alpino_miniapp.html"
    if not file_path.exists():
        return web.Response(
            text="alpino_miniapp.html topilmadi - bot/webapp/static/ papkasiga joylashtirilganini tekshiring",
            status=500,
        )
    return web.FileResponse(file_path)


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/health", health_check)
    app.router.add_get("/alpino", serve_alpino)
    # TODO (Alpino TZ v3, 5-bo'lim): bu yerga /alpino/* API endpoint'lari
    # (POST /alpino/market/order va h.k.) qo'shib boriladi
    return app


async def run_webapp(port: int) -> None:
    """Serverni fon vazifasi (background task) sifatida ishga tushiradi.
    Bloklamaydi - darhol qaytadi, server orqa fonda ishlab turadi."""
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    logger.info(f"Alpino webapp {port}-portda ishga tushdi (/alpino va /health faol)")
