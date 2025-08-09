"""align schema to models: schedules->shifts, make employee_id nullable, add locations.order"""

from alembic import op
import sqlalchemy as sa

revision = '0002_align_to_models'
down_revision = '0001_init'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # 1) Переименовать schedules -> shifts (если еще не переименовано)
    tables = inspector.get_table_names()
    if "schedules" in tables and "shifts" not in tables:
        op.rename_table("schedules", "shifts")

    # 2) Сделать employee_id nullable в shifts — через batch (SQLite)
    if "shifts" in inspector.get_table_names():
        with op.batch_alter_table("shifts", recreate="always") as batch_op:
            batch_op.alter_column(
                "employee_id",
                existing_type=sa.Integer(),
                nullable=True,
                existing_nullable=False,
            )

    # 3) Добавить locations.order (если нет)
    loc_cols = set(c["name"] for c in inspector.get_columns("locations"))
    if "order" not in loc_cols:
        op.add_column(
            "locations",
            sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
        )
        # убираем default, чтобы не оставался на будущее
        op.alter_column("locations", "order", server_default=None)


def downgrade():
    # 3) Удалить locations.order
    op.drop_column("locations", "order")

    # 2) Вернуть employee_id NOT NULL — тоже через batch
    with op.batch_alter_table("shifts", recreate="always") as batch_op:
        batch_op.alter_column(
            "employee_id",
            existing_type=sa.Integer(),
            nullable=False,
            existing_nullable=True,
        )

    # 1) Переименовать shifts обратно в schedules
    op.rename_table("shifts", "schedules")
