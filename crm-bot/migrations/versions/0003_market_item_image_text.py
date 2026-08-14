"""alpino: market mahsulot rasmi ustunini TEXT ga o'zgartirish

Miniapp rasmni base64 (data:image/...) shaklida yuboradi, bu odatda
bir necha ming belgi bo'ladi. image_url String(500) bo'lgani uchun
Postgres StringDataRightTruncationError xatosini berardi va "Yangi
mahsulot qo'shish" hamda mavjud mahsulotga rasm yuklash ishlamay
qolgan edi.

Revision ID: 0003_market_item_image_text
Revises: 0002_alpino_market_catalog
Create Date: 2026-08-14

"""
from alembic import op
import sqlalchemy as sa

revision = "0003_market_item_image_text"
down_revision = "0002_alpino_market_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "alpino_market_items",
        "image_url",
        existing_type=sa.String(500),
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
