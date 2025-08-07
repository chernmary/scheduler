import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db_base import Base

# Получаем абсолютный путь к текущей папке (где лежит database.py)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Строим абсолютный путь к файлу базы данных
SQLALCHEMY_DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'scheduler.db')}"

# Создаём движок SQLAlchemy
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# Создаём сессию для работы с БД
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Функция инициализации базы: создаёт таблицы по моделям
def init_db():
    from app import models  # Импорт моделей внутри функции, чтобы избежать циклов
    Base.metadata.create_all(bind=engine)
