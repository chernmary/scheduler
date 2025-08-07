import os
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine

def run_migrations():
    # Абсолютный путь к БД
    db_path = os.path.join(os.getcwd(), "scheduler.db")
    db_url = f"sqlite:///{db_path}"

    # Если базы нет — создадим пустую
    if not os.path.exists(db_path):
        engine = create_engine(db_url, connect_args={"check_same_thread": False})
        engine.connect().close()  # просто создаём файл

    # Настраиваем Alembic
    alembic_cfg = Config(os.path.join("migrations", "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # Запускаем миграции
    command.upgrade(alembic_cfg, "head")
