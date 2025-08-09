"""align schema to models: schedules->shifts, make employee_id nullable, add locations.order (SQLite-safe)"""

from alembic import op
import sqlalchemy as sa

revision = "0002_align_to_models"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    # 1) Переименовать schedules -> shifts (если еще не)
    tables = insp.get_table_names()
    if "schedules" in tables and "shifts" not in tables:
        op.rename_table("schedules", "shifts")

    # 2) shifts.employee_id -> NULLABLE (через batch для SQLite)
    if "shifts" in insp.get_table_names():
        with op.batch_alter_table("shifts", recreate="always") as b:
            b.alter_column(
                "employee_id",
                existing_type=sa.Integer(),
                nullable=True,
                existing_nullable=False,
            )

    # 3) locations."order"
    loc_cols = {c["name"] for c in insp.get_columns("locations")}
    if "order" not in loc_cols:
        # сначала добавим колонку nullable с дефолтом (чтобы проинициализировать значения)
        op.add_column(
            "locations",
            sa.Column("order", sa.Integer(), nullable=True, server_default="0"),
        )
        # проинициализируем чем-то осмысленным (например, id)
        op.execute(sa.text('UPDATE locations SET "order" = COALESCE("order", id)'))

        # теперь уберем дефолт и сделаем NOT NULL, НО через batch (пересоздание таблицы)
        with op.batch_alter_table("locations", recreate="always") as b:
            b.alter_column(
                "order",
                existing_type=sa.Integer(),
                nullable=False,
                server_default=None,
            )


def downgrade():
    # 3) вернуть все назад для locations
    with op.batch_alter_table("locations", recreate="always") as b:
        b.drop_column("order")

    # 2) вернуть NOT NULL для shifts.employee_id
    with op.batch_alter_table("shifts", recreate="always") as b:
        b.alter_column(
            "employee_id",
            existing_type=sa.Integer(),
            nullable=False,
            existing_nullable=True,
        )

    # 1) переименовать обратно
    op.rename_table("shifts", "schedules")
