"""alpino: market mahsulot rasmi ustunini TEXT ga o'zgartirish

Miniapp rasmni base64 (data:image/...) shaklida yuboradi, bu odatda
bir necha ming belgi bo'ladi. image_url String(500) bo'lgani uchun
Postgres StringDataRightTruncationError xatosini berardi va "Yangi
mahsulot qo'shish" hamda mavjud mahsulotga rasm yuklash ishlamay
qolgan edi.

Revision ID: 0003_market_item_image_text
Revises: 0002_alpino_market_catalog
Create Date: 2026-08-14

MUHIM (2026-08-17 tuzatildi): idempotent qilindi - agar ustun allaqachon
TEXT bo'lsa (masalan model.py o'zgarishi bilan create_all() orqali to'g'ridan
TEXT sifatida yaratilgan bo'lsa), qayta ALTER qilishga urinmaydi.
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_market_item_image_text"
down_revision = "0002_alpino_market_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"]: c for c in inspector.get_columns("alpino_market_items")}
    current_type = columns.get("image_url", {}).get("type")

    # Agar ustun allaqachon TEXT (yoki unga o'xshash cheklovsiz turdagi) bo'lsa,
    # qayta o'zgartirishga hojat yo'q.
    if isinstance(current_type, sa.String) and not isinstance(current_type, sa.Text):
        op.alter_column(
            "alpino_market_items",
            "image_url",
            existing_type=sa.String(current_type.length or 500),
            type_=sa.Text(),
            existing_nullable=True,
        )


def downgrade() -> None:
    # Diqqat: agar bazada 500 belgidan uzun rasm saqlangan bo'lsa, bu
    # qadam xato beradi (avval uzun qiymatlarni tozalash kerak bo'ladi).
    op.alter_column(
        "alpino_market_items",
        "image_url",
        existing_type=sa.Text(),
        type_=sa.String(500),
        existing_nullable=True,
    )
