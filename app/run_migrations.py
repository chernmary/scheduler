import os
from alembic import command
from alembic.config import Config

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

alembic_cfg = Config(os.path.join(BASE_DIR, '../migrations/alembic.ini'))


db_path = os.path.join(BASE_DIR, "scheduler.db")
alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

command.upgrade(alembic_cfg, "head")
