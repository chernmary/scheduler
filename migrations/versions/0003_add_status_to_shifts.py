"""add status column to shifts table

Revision ID: 0003_add_status_to_shifts
Revises: 0002_align_to_models
Create Date: 2025-08-10

"""
from alembic import op
import sqlalchemy as sa


# ID этой миграции
revision = "0003_add_status_to_shifts"
# Ссылаемся на предыдущую
down_revision = "0002_align_to_models"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if "shifts" in insp.get_table_names():
        # Добавляем колонку status с дефолтом draft
        op.add_column(
            "shifts",
            sa.Column("status", sa.String(length=20), nullable=False, server_default="draft")
        )

        # Обновляем все старые смены — они становятся опубликованными
        op.execute(sa.text("UPDATE shifts SET status = 'published'"))


def downgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if "shifts" in insp.get_table_names():
        with op.batch_alter_table("shifts", recreate="always") as b:
            b.drop_column("status")
