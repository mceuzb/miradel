"""alpino: market katalogi + referral oylik bonus nazorati + izoh maydoni

Revision ID: 0002_alpino_market_catalog
Revises: 0001_baseline
Create Date: 2026-08-14

MUHIM (2026-08-17 tuzatildi): bu jadval/ustunlar production bazasida
alembic orqali EMAS, balki ilova ishga tushganda avtomatik chaqiriladigan
`Base.metadata.create_all()` orqali allaqachon yaratilgan edi. alembic_version
esa shtamplanmagan qolgan edi. Shu sabab, `alembic upgrade head` birinchi
marta ishga tushirilganda bu migratsiya "relation already exists" xatosi
bilan qulab tushdi. Shuning uchun bu migratsiya IDEMPOTENT qilib qayta
yozildi - har bir amaldan oldin obyekt bazada bor-yo'qligini tekshiradi va
mavjud bo'lsa o'tkazib yuboradi. Yangi (bo'sh) bazada ham, eski
(create_all() orqali qisman to'ldirilgan) bazada ham xavfsiz ishlaydi.
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_alpino_market_catalog"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def _table_exists(inspector, name: str) -> bool:
    return name in inspector.get_table_names()


def _column_exists(inspector, table: str, column: str) -> bool:
    return column in [c["name"] for c in inspector.get_columns(table)]


def _fk_exists(inspector, table: str, fk_name: str) -> bool:
    return fk_name in [fk["name"] for fk in inspector.get_foreign_keys(table)]


def _unique_exists(inspector, table: str, uq_name: str) -> bool:
    return uq_name in [uq["name"] for uq in inspector.get_unique_constraints(table)]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1) Market katalogi - hozirgi holatda AlpinoMarketOrder ichida item_name/
    #    cost_points qo'lda yozilgan, admin narx/son boshqara olmaydi. Endi
    #    alohida katalog jadvali qo'shiladi (yangi jadval - xavfsiz, mavjud
    #    ma'lumotlarga tegmaydi).
    if not _table_exists(inspector, "alpino_market_items"):
        op.create_table(
            "alpino_market_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("image_url", sa.String(500), nullable=True),
            sa.Column("cost_points", sa.Integer(), nullable=False),
            sa.Column("condition_text", sa.String(255), nullable=True),
            sa.Column("stock", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("tier", sa.String(32), nullable=False, server_default="silver"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
        inspector = sa.inspect(bind)

    # 2) AlpinoMarketOrder endi katalogga bog'lanadi (item_id). Eski
    #    item_name/cost_points ustunlari TARIXIY sifatida qoladi (buyurtma
    #    vaqtidagi nom/narx saqlanishi kerak, katalogda keyin o'zgarsa ham).
    if not _column_exists(inspector, "alpino_market_orders", "item_id"):
        op.add_column("alpino_market_orders", sa.Column("item_id", sa.Integer(), nullable=True))
        inspector = sa.inspect(bind)

    if not _fk_exists(inspector, "alpino_market_orders", "fk_alpino_market_orders_item_id"):
        op.create_foreign_key(
            "fk_alpino_market_orders_item_id",
            "alpino_market_orders", "alpino_market_items",
            ["item_id"], ["id"],
        )
        inspector = sa.inspect(bind)

    # 3) Referral: bir oyda 2-to'lov bonusini (+300) ikki marta bermaslik
    #    uchun nazorat ustuni.
    if not _column_exists(inspector, "alpino_referrals", "paid_bonus_month"):
        op.add_column("alpino_referrals", sa.Column("paid_bonus_month", sa.String(7), nullable=True))
        inspector = sa.inspect(bind)

    # 4) Bitta odam faqat bir marta referral sifatida qo'shilishi (xavfsizlik/
    #    integritet uchun) - agar mavjud ma'lumotlarda takror bo'lsa, bu qadam
    #    xato beradi, shunda avval takrorlarni qo'lda tozalash kerak bo'ladi.
    if not _unique_exists(inspector, "alpino_referrals", "uq_alpino_referred_once"):
        op.create_unique_constraint(
            "uq_alpino_referred_once", "alpino_referrals", ["referred_id"]
        )
        inspector = sa.inspect(bind)

    # 5) O'qituvchi ball taklif qilganda izoh qoldira olishi uchun.
    if not _column_exists(inspector, "alpino_points_history", "comment"):
        op.add_column("alpino_points_history", sa.Column("comment", sa.Text(), nullable=True))
        inspector = sa.inspect(bind)

    # 6) Buyurtma qachon oflayn topshirilgani (fulfil qilingani).
    if not _column_exists(inspector, "alpino_market_orders", "delivered_at"):
        op.add_column("alpino_market_orders", sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("alpino_market_orders", "delivered_at")
    op.drop_column("alpino_points_history", "comment")
    op.drop_constraint("uq_alpino_referred_once", "alpino_referrals", type_="unique")
    op.drop_column("alpino_referrals", "paid_bonus_month")
    op.drop_constraint("fk_alpino_market_orders_item_id", "alpino_market_orders", type_="foreignkey")
    op.drop_column("alpino_market_orders", "item_id")
    op.drop_table("alpino_market_items")
