"""referral: admin tomonidan qo'lda qo'shiladigan (ommaviy reytingda
ko'rinmaydigan) bonus ball uchun ustunlar

Admin asosiy referal konkursiga xohlagan foydalanuvchiga qo'shimcha ball
qo'sha oladigan bo'ldi. Bu ballar umumiy (ommaviy "🏆 Reyting") ko'rinishda
HISOBGA OLINMAYDI, lekin konkurs g'oliblarini aniqlashda va admin panelidagi
reytingda ishtirok etadi.

Revision ID: 0004_referral_admin_bonus
Revises: 0003_market_item_image_text
Create Date: 2026-08-17

"""
from alembic import op
import sqlalchemy as sa

revision = "0004_referral_admin_bonus"
down_revision = "0003_market_item_image_text"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "referral_points_ledger",
        sa.Column("is_admin_bonus", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "referral_points_ledger",
        sa.Column("admin_note", sa.String(255), nullable=True),
    )
    op.alter_column(
        "referral_points_ledger",
        "source_referred_telegram_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "referral_points_ledger",
        "source_referred_telegram_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
    op.drop_column("referral_points_ledger", "admin_note")
    op.drop_column("referral_points_ledger", "is_admin_bonus")
