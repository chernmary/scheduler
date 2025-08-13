"""add status to shift unique constraint"""

from alembic import op
import sqlalchemy as sa

# Revision identifiers, used by Alembic.
revision = "0004_add_status_to_unique_constraint"
down_revision = "0003_add_status_to_shifts"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if "shifts" in insp.get_table_names():
        with op.batch_alter_table("shifts", recreate="always") as batch:
            # Удаляем старую уникальность по (date, location_id), если она была
            try:
                batch.drop_constraint("uix_date_location", type_="unique")
            except Exception:
                # В SQLite это мог быть индекс с таким именем
                try:
                    op.drop_index("uix_date_location", table_name="shifts")
                except Exception:
                    pass

            # Удаляем возможные дубликаты перед созданием новой уникальности
            op.execute(
                """
DELETE FROM shifts
WHERE rowid NOT IN (
    SELECT MIN(rowid)
    FROM shifts
    GROUP BY date, location_id, status
)
"""
            )

# Создаём новую уникальность по (date, location_id, status)
            batch.create_unique_constraint(
                "uix_date_location_status",
                ["date", "location_id", "status"],
            )


def downgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if "shifts" in insp.get_table_names():
        with op.batch_alter_table("shifts", recreate="always") as batch:
            # Удаляем новую уникальность
            try:
                batch.drop_constraint("uix_date_location_status", type_="unique")
            except Exception:
                try:
                    op.drop_index("uix_date_location_status", table_name="shifts")
                except Exception:
                    pass

            # Возвращаем прежнюю уникальность по (date, location_id)
            batch.create_unique_constraint(
                "uix_date_location",
                ["date", "location_id"],
            )
