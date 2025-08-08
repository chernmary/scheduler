from alembic import command
from alembic.config import Config
import os

def run_migrations():
    # Создаём абсолютный путь к alembic.ini
    base_dir = os.path.dirname(os.path.abspath(__file__))
    alembic_ini_path = os.path.join(base_dir, "..", "migrations", "alembic.ini")

    # Создаём конфигурацию Alembic
    alembic_cfg = Config(alembic_ini_path)

    # Явно указываем путь к папке миграций и URL базы данных
    migrations_path = os.path.join(base_dir, "..", "migrations")
    alembic_cfg.set_main_option("script_location", migrations_path)
    alembic_cfg.set_main_option("sqlalchemy.url", "sqlite:///scheduler.db")

    # Применяем миграции до актуальной версии
    command.upgrade(alembic_cfg, "head")

if __name__ == "__main__":
    run_migrations()
