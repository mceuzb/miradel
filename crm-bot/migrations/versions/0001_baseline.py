"""baseline - mavjud bazani boshlang'ich nuqta sifatida belgilaydi

Revision ID: 0001_baseline
Revises:
Create Date: 2026-08-14

Bu migratsiya HECH NARSA o'zgartirmaydi. Barcha jadvallar bu paytga qadar
`Base.metadata.create_all()` orqali allaqachon yaratilgan. Bu faqat Alembic
uchun "nol nuqta" - shundan keyingi barcha o'zgarishlar (yangi ustun/jadval)
haqiqiy migratsiya fayllari orqali, boshqariladigan holda amalga oshiriladi.
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
