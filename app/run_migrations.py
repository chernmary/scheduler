import os
from alembic.config import Config
from alembic import command

def run_migrations():
    # Указываем путь к alembic.ini (он лежит в папке migrations)
    alembic_cfg = Config(os.path.join("migrations", "alembic.ini"))

    # Получаем абсолютный путь к базе данных scheduler.db
    project_root = os.getcwd()  # Render всегда запускает из корня проекта
    db_path = os.path.join(project_root, "scheduler.db")

    # Вставляем в конфигурацию путь к базе
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

    # Запускаем миграции
    command.upgrade(alembic_cfg, "head")
