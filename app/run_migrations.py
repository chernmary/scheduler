import os
from sqlalchemy import create_engine
from alembic.config import Config
from alembic import command

# 1. Определяем корень проекта
project_root = os.path.dirname(os.path.abspath(__file__))

# 2. Формируем путь к базе данных (если используем SQLite)
db_path = os.path.join(project_root, "scheduler.db")
db_url = f"sqlite:///{db_path}"

# 3. Создаём файл базы данных, если он не существует
if not os.path.exists(db_path):
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    engine.connect().close()

# 4. Указываем Alembic, где находится конфигурация
alembic_cfg = Config(os.path.join(project_root, "migrations", "alembic.ini"))
alembic_cfg.set_main_option("sqlalchemy.url", db_url)

# 5. Запускаем миграции
command.upgrade(alembic_cfg, "head")
