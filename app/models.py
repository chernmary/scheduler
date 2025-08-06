from sqlalchemy import Column, Integer, String, Date, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.dp_base import Base  # база теперь импортируется отсюда

# 🧍 Сотрудник
class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    birth_date = Column(Date, nullable=True)
    phone = Column(String, nullable=True)
    telegram_nick = Column(String, nullable=True)
    notes = Column(String, nullable=True)

    medical_book_expiry = Column(Date, nullable=True)
    on_sick_leave = Column(Boolean, default=False)
    is_helper = Column(Boolean, default=False)

    shifts = relationship("Shift", back_populates="employee", cascade="all, delete")
    settings = relationship("EmployeeSetting", back_populates="employee", cascade="all, delete")

# 📍 Локация
class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    order = Column(Integer, nullable=False)  # для отображения в нужном порядке
    zone = Column(String, nullable=False)


    shifts = relationship("Shift", back_populates="location", cascade="all, delete")

# 📅 Смена
class Shift(Base):
    __tablename__ = "shifts"

    id = Column(Integer, primary_key=True, index=True)

    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    employee = relationship("Employee", back_populates="shifts")

    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    location = relationship("Location", back_populates="shifts")

    date = Column(Date, nullable=False)
    shift_type = Column(String, nullable=True)  # если появятся типы смен
    is_template = Column(Boolean, default=False)

# ⚙️ Настройки и ограничения для сотрудников
class EmployeeSetting(Base):
    __tablename__ = "employee_settings"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)

    is_preferred = Column(Boolean, default=False)  # предпочитаем работать здесь
    is_allowed = Column(Boolean, default=True)     # можно ли работать в этой локации

    employee = relationship("Employee", back_populates="settings")
    location = relationship("Location")

