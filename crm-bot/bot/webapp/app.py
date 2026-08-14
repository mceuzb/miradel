"""Alpino Mini App uchun aiohttp web-server (TZ v3, 4-5-bo'limlar).

MUHIM: `run_webapp()` HECH QACHON to'g'ridan-to'g'ri `await` qilinmasin -
main.py'da `asyncio.create_task(run_webapp(...))` orqali FON vazifasi
sifatida ishga tushiriladi, aks holda botning polling sikli boshlanmay qoladi.
"""

import logging
import pathlib

from aiohttp import web
from sqlalchemy import select

from bot.config import get_config
from bot.database.engine import async_session
from bot.database.models import (
    AlpinoCategoryLimit, AlpinoFunnelEvent, AlpinoMarketItem, AlpinoMarketOrder,
    AlpinoOrderStatus, AlpinoPointsHistory, AlpinoPointsStatus, User, UserRole, UserStatus,
)
from bot.services import alpino_service
from bot.services.alpino_access import alpino_access_allowed
from bot.webapp.webapp_auth import verify_init_data

logger = logging.getLogger(__name__)

STATIC_DIR = pathlib.Path(__file__).parent / "static"


# ---------------------------------------------------------------------------
# Auth middleware - har bir /alpino/* so'rovda initData tekshiriladi
# ---------------------------------------------------------------------------

@web.middleware
async def alpino_error_middleware(request: web.Request, handler):
    """VAQTINCHA DIAGNOSTIKA: kutilmagan (500) xatolarni ham JSON ko'rinishida
    qaytaradi - aks holda aiohttp ularni oddiy matn sifatida qaytaradi va
    frontend "Server javobi noto'g'ri" deb umumiy xato ko'rsatadi, haqiqiy
    sabab yashiringan bo'ladi. Muammo topilgach bu middleware olib tashlanadi
    (production'da xato tafsilotlarini foydalanuvchiga ko'rsatish yaxshi amaliyot
    emas)."""
    try:
        return await handler(request)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.exception("ALPINO 500: %s %s", request.method, request.path)
        return web.json_response(
            {"ok": False, "error": "server_error", "message": f"{type(e).__name__}: {e}"},
            status=500,
        )


@web.middleware
async def alpino_auth_middleware(request: web.Request, handler):
    if not request.path.startswith("/alpino/") and request.path != "/alpino":
        return await handler(request)

    if request.path == "/alpino":
        # HTML sahifaning o'zi - auth shart emas, mini app o'zi ichidan API'ga murojaat qiladi
        return await handler(request)

    init_data = request.headers.get("X-Telegram-Init-Data", "")
    # ===== VAQTINCHA DEBUG (muammo topilgach olib tashlanadi) =====
    logger.info(f"ALPINO DEBUG: initData uzunligi={len(init_data)}, boshi={init_data[:80]!r}")

    config = get_config()
    parsed = verify_init_data(init_data, config.bot_token)
    if parsed is None:
        return web.json_response({"ok": False, "error": "unauthorized", "message": "initData yaroqsiz"}, status=401)

    telegram_user = parsed.get("user", {})
    telegram_id = telegram_user.get("id")
    if telegram_id is None:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=401)

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
        if user is None or user.status != UserStatus.APPROVED:
            return web.json_response(
                {"ok": False, "error": "not_registered", "message": "Ro'yxatdan o'tmagansiz"}, status=403
            )
        if not await alpino_access_allowed(session, user.role):
            return web.json_response(
                {"ok": False, "error": "module_disabled", "message": "Alpino hozircha faol emas"}, status=403
            )
        request["session"] = session
        request["user"] = user
        return await handler(request)


# ---------------------------------------------------------------------------
# Static / health
# ---------------------------------------------------------------------------

async def health_check(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def serve_alpino(request: web.Request) -> web.Response:
    file_path = STATIC_DIR / "alpino_miniapp.html"
    if not file_path.exists():
        return web.Response(text="alpino_miniapp.html topilmadi", status=500)
    return web.FileResponse(file_path)


# ---------------------------------------------------------------------------
# O'quvchi endpoint'lari
# ---------------------------------------------------------------------------

def _serialize_user(user: User, balance: int) -> dict:
    return {
        "id": user.id,
        "full_name": user.full_name,
        "role": user.role.value,
        "balance": balance,
    }


async def alpino_me(request: web.Request) -> web.Response:
    session, user = request["session"], request["user"]
    balance = await alpino_service.get_balance(session, user)
    return web.json_response({"ok": True, "data": _serialize_user(user, balance)})


async def alpino_market(request: web.Request) -> web.Response:
    session = request["session"]
    items = await session.scalars(
        select(AlpinoMarketItem).where(AlpinoMarketItem.is_active == True).order_by(AlpinoMarketItem.cost_points)  # noqa: E712
    )
    data = [
        {
            "id": i.id, "name": i.name, "image_url": i.image_url,
            "cost_points": i.cost_points, "condition_text": i.condition_text,
            "stock": i.stock, "tier": i.tier,
        }
        for i in items.all()
    ]
    return web.json_response({"ok": True, "data": data})


async def alpino_market_order(request: web.Request) -> web.Response:
    session, user = request["session"], request["user"]
    if user.role != UserRole.STUDENT:
        return web.json_response({"ok": False, "error": "forbidden"}, status=403)
    body = await request.json()
    item_id = body.get("item_id")
    try:
        order = await alpino_service.buy_item(session, user=user, item_id=item_id)
    except alpino_service.AlpinoError as e:
        return web.json_response({"ok": False, "error": "bad_request", "message": str(e)}, status=400)
    return web.json_response({"ok": True, "data": {"order_id": order.id, "status": order.status.value}})


async def alpino_leaderboard(request: web.Request) -> web.Response:
    session = request["session"]
    from sqlalchemy import func as sa_func
    rows = await session.execute(
        select(User.id, User.full_name, sa_func.sum(AlpinoPointsHistory.amount).label("total"))
        .join(AlpinoPointsHistory, AlpinoPointsHistory.user_id == User.id)
        .where(AlpinoPointsHistory.status == AlpinoPointsStatus.APPROVED, User.status == UserStatus.APPROVED)
        .group_by(User.id, User.full_name)
        .order_by(sa_func.sum(AlpinoPointsHistory.amount).desc())
        .limit(10)
    )
    data = [{"user_id": r.id, "full_name": r.full_name, "points": int(r.total)} for r in rows.all()]
    return web.json_response({"ok": True, "data": data})


async def alpino_pending(request: web.Request) -> web.Response:
    session, user = request["session"], request["user"]
    rows = await session.scalars(
        select(AlpinoPointsHistory)
        .where(AlpinoPointsHistory.user_id == user.id, AlpinoPointsHistory.status == AlpinoPointsStatus.PENDING)
        .order_by(AlpinoPointsHistory.created_at.desc())
    )
    data = [
        {"id": r.id, "category": r.category, "amount": r.amount, "comment": r.comment}
        for r in rows.all()
    ]
    return web.json_response({"ok": True, "data": data})


async def alpino_history(request: web.Request) -> web.Response:
    session, user = request["session"], request["user"]
    rows = await session.scalars(
        select(AlpinoPointsHistory)
        .where(AlpinoPointsHistory.user_id == user.id, AlpinoPointsHistory.status != AlpinoPointsStatus.PENDING)
        .order_by(AlpinoPointsHistory.created_at.desc())
        .limit(50)
    )
    data = [
        {
            "id": r.id, "category": r.category, "amount": r.amount,
            "status": r.status.value, "reject_reason": r.reject_reason,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows.all()
    ]
    return web.json_response({"ok": True, "data": data})


async def alpino_referral(request: web.Request) -> web.Response:
    session, user = request["session"], request["user"]
    from bot.database.models import AlpinoReferral, AlpinoReferralStatus
    from sqlalchemy import func as sa_func

    config = get_config()
    link = f"https://t.me/{config.bot_username}?start=alpino_{user.id}" if config.bot_username else None

    referred_count = await session.scalar(
        select(sa_func.count(AlpinoReferral.id)).where(AlpinoReferral.referrer_id == user.id)
    ) or 0
    paid_count = await session.scalar(
        select(sa_func.count(AlpinoReferral.id)).where(
            AlpinoReferral.referrer_id == user.id, AlpinoReferral.status == AlpinoReferralStatus.PAID,
        )
    ) or 0
    total_points = await session.scalar(
        select(sa_func.coalesce(sa_func.sum(AlpinoPointsHistory.amount), 0)).where(
            AlpinoPointsHistory.user_id == user.id,
            AlpinoPointsHistory.category.in_(["referral_kelish", "referral_tolov"]),
            AlpinoPointsHistory.status == AlpinoPointsStatus.APPROVED,
        )
    ) or 0

    return web.json_response({
        "ok": True,
        "data": {
            "link": link, "referred_count": referred_count,
            "paid_count": paid_count, "total_points": int(total_points),
        },
    })


# ---------------------------------------------------------------------------
# Admin endpoint'lari
# ---------------------------------------------------------------------------

def _require_admin(user: User) -> web.Response | None:
    if user.role != UserRole.ADMIN:
        return web.json_response({"ok": False, "error": "forbidden"}, status=403)
    return None


async def admin_approvals(request: web.Request) -> web.Response:
    session, user = request["session"], request["user"]
    if (err := _require_admin(user)) is not None:
        return err
    rows = await session.scalars(
        select(AlpinoPointsHistory)
        .where(AlpinoPointsHistory.status == AlpinoPointsStatus.PENDING)
        .order_by(AlpinoPointsHistory.created_at)
    )
    data = []
    for r in rows.all():
        student = await session.get(User, r.user_id)
        teacher = await session.get(User, r.teacher_id) if r.teacher_id else None
        data.append({
            "id": r.id, "student_name": student.full_name if student else "?",
            "teacher_name": teacher.full_name if teacher else "?",
            "category": r.category, "amount": r.amount, "comment": r.comment,
        })
    return web.json_response({"ok": True, "data": data})


async def admin_approval_action(request: web.Request) -> web.Response:
    session, user = request["session"], request["user"]
    if (err := _require_admin(user)) is not None:
        return err
    entry_id = int(request.match_info["id"])
    body = await request.json()
    action = body.get("action")
    try:
        if action == "approve":
            await alpino_service.approve_points(session, entry_id=entry_id, admin=user)
        elif action == "reject":
            await alpino_service.reject_points(session, entry_id=entry_id, admin=user, reason=body.get("reason", ""))
        else:
            return web.json_response({"ok": False, "error": "bad_request", "message": "action noto'g'ri"}, status=400)
    except alpino_service.AlpinoError as e:
        return web.json_response({"ok": False, "error": "bad_request", "message": str(e)}, status=400)
    return web.json_response({"ok": True})


async def admin_market_create(request: web.Request) -> web.Response:
    session, user = request["session"], request["user"]
    if (err := _require_admin(user)) is not None:
        return err
    body = await request.json()
    item = AlpinoMarketItem(
        name=body.get("name", ""),
        image_url=body.get("image_url"),
        cost_points=int(body.get("cost_points", 0)),
        condition_text=body.get("condition_text"),
        stock=int(body.get("stock", 0)),
        tier=body.get("tier", "silver"),
    )
    if not item.name or item.cost_points <= 0:
        return web.json_response({"ok": False, "error": "bad_request", "message": "nom/narx noto'g'ri"}, status=400)
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return web.json_response({"ok": True, "data": {"id": item.id}})


async def admin_market_update(request: web.Request) -> web.Response:
    session, user = request["session"], request["user"]
    if (err := _require_admin(user)) is not None:
        return err
    item = await session.get(AlpinoMarketItem, int(request.match_info["id"]))
    if item is None:
        return web.json_response({"ok": False, "error": "not_found"}, status=404)
    body = await request.json()
    for field in ("name", "image_url", "cost_points", "condition_text", "stock", "tier", "is_active"):
        if field in body:
            setattr(item, field, body[field])
    await session.commit()
    return web.json_response({"ok": True})


async def admin_market_delete(request: web.Request) -> web.Response:
    session, user = request["session"], request["user"]
    if (err := _require_admin(user)) is not None:
        return err
    item = await session.get(AlpinoMarketItem, int(request.match_info["id"]))
    if item is None:
        return web.json_response({"ok": False, "error": "not_found"}, status=404)
    item.is_active = False  # yumshoq o'chirish - eski buyurtmalar tarixi buzilmasin
    await session.commit()
    return web.json_response({"ok": True})


async def admin_orders(request: web.Request) -> web.Response:
    session, user = request["session"], request["user"]
    if (err := _require_admin(user)) is not None:
        return err
    status_filter = request.query.get("status", "pending")
    status_enum = AlpinoOrderStatus.PENDING if status_filter == "pending" else AlpinoOrderStatus.DELIVERED
    rows = await session.scalars(
        select(AlpinoMarketOrder).where(AlpinoMarketOrder.status == status_enum).order_by(AlpinoMarketOrder.created_at)
    )
    data = []
    for o in rows.all():
        buyer = await session.get(User, o.user_id)
        data.append({
            "id": o.id, "buyer_name": buyer.full_name if buyer else "?",
            "item_name": o.item_name, "cost_points": o.cost_points,
        })
    return web.json_response({"ok": True, "data": data})


async def admin_order_fulfil(request: web.Request) -> web.Response:
    session, user = request["session"], request["user"]
    if (err := _require_admin(user)) is not None:
        return err
    try:
        await alpino_service.fulfil_order(session, order_id=int(request.match_info["id"]))
    except alpino_service.AlpinoError as e:
        return web.json_response({"ok": False, "error": "bad_request", "message": str(e)}, status=400)
    return web.json_response({"ok": True})


# Frontenddagi "Chegara" panelida ko'rsatiladigan toifalar - agar bazada
# hali sozlanmagan bo'lsa, shu standart qiymatlar ko'rsatiladi.
DEFAULT_CATEGORY_LIMITS = {
    "vazifa": 3, "topshiriq": 5, "imtihon": 15, "dars_faolligi": 10,
}
CATEGORY_LABELS = {
    "vazifa": "Vazifa", "topshiriq": "Topshiriq",
    "imtihon": "Imtihon", "dars_faolligi": "Dars faolligi g'olibi",
}


async def admin_limits(request: web.Request) -> web.Response:
    session, user = request["session"], request["user"]
    if (err := _require_admin(user)) is not None:
        return err
    rows = await session.scalars(select(AlpinoCategoryLimit))
    saved = {r.category: r.max_points for r in rows.all()}
    data = [
        {"category": cat, "label": CATEGORY_LABELS[cat], "max_points": saved.get(cat, default)}
        for cat, default in DEFAULT_CATEGORY_LIMITS.items()
    ]
    return web.json_response({"ok": True, "data": data})


async def admin_limits_update(request: web.Request) -> web.Response:
    session, user = request["session"], request["user"]
    if (err := _require_admin(user)) is not None:
        return err
    body = await request.json()  # {"vazifa": 3, "topshiriq": 5, ...}
    for category, value in body.items():
        if category not in DEFAULT_CATEGORY_LIMITS:
            continue
        try:
            value_int = int(value)
        except (TypeError, ValueError):
            continue
        row = await session.scalar(select(AlpinoCategoryLimit).where(AlpinoCategoryLimit.category == category))
        if row is None:
            session.add(AlpinoCategoryLimit(category=category, max_points=value_int, set_by_admin_id=user.id))
        else:
            row.max_points = value_int
            row.set_by_admin_id = user.id
    await session.commit()
    return web.json_response({"ok": True})


async def admin_alerts(request: web.Request) -> web.Response:
    session, user = request["session"], request["user"]
    if (err := _require_admin(user)) is not None:
        return err
    # TODO: haqiqiy anomaliya aniqlash mantig'i (masalan bitta o'qituvchining
    # o'rtacha bergan bali guruh o'rtachasidan sezilarli farq qilishi) -
    # bu keyingi bosqichda alohida qo'shiladi. Hozircha bo'sh ro'yxat.
    return web.json_response({"ok": True, "data": []})


async def admin_kpi(request: web.Request) -> web.Response:
    session, user = request["session"], request["user"]
    if (err := _require_admin(user)) is not None:
        return err
    from sqlalchemy import func as sa_func
    blocked = await session.scalar(
        select(sa_func.count(AlpinoFunnelEvent.id)).where(AlpinoFunnelEvent.event == "blocked_unregistered")
    ) or 0
    enrolled = await session.scalar(
        select(sa_func.count(AlpinoFunnelEvent.id)).where(AlpinoFunnelEvent.event == "enrolled")
    ) or 0
    return web.json_response({"ok": True, "data": {"blocked_unregistered": blocked, "enrolled": enrolled}})


# ---------------------------------------------------------------------------
# App yaratish / ishga tushirish
# ---------------------------------------------------------------------------

def create_app() -> web.Application:
    app = web.Application(middlewares=[alpino_error_middleware, alpino_auth_middleware])
    app.router.add_get("/health", health_check)
    app.router.add_get("/alpino", serve_alpino)

    app.router.add_get("/alpino/me", alpino_me)
    app.router.add_get("/alpino/market", alpino_market)
    app.router.add_post("/alpino/market/order", alpino_market_order)
    app.router.add_get("/alpino/leaderboard", alpino_leaderboard)
    app.router.add_get("/alpino/pending", alpino_pending)
    app.router.add_get("/alpino/history", alpino_history)
    app.router.add_get("/alpino/referral", alpino_referral)

    app.router.add_get("/alpino/admin/approvals", admin_approvals)
    app.router.add_post("/alpino/admin/approvals/{id}", admin_approval_action)
    app.router.add_post("/alpino/admin/market", admin_market_create)
    app.router.add_patch("/alpino/admin/market/{id}", admin_market_update)
    app.router.add_delete("/alpino/admin/market/{id}", admin_market_delete)
    app.router.add_get("/alpino/admin/orders", admin_orders)
    app.router.add_post("/alpino/admin/orders/{id}/fulfil", admin_order_fulfil)
    app.router.add_get("/alpino/admin/limits", admin_limits)
    app.router.add_post("/alpino/admin/limits", admin_limits_update)
    app.router.add_get("/alpino/admin/alerts", admin_alerts)
    app.router.add_get("/alpino/admin/kpi", admin_kpi)

    return app


async def run_webapp(port: int) -> None:
    """Fon vazifasi sifatida ishga tushadi - bloklamaydi."""
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    logger.info(f"Alpino webapp {port}-portda ishga tushdi")
