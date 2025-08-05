from sqlalchemy import Column, Integer, String, Boolean, Date, ForeignKey, Text
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    display_order = Column(Integer, nullable=False)

    def _repr_(self):
        return f"<Location(name={self.name})>"

class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True)
    full_name = Column(String, nullable=False)
    birth_date = Column(Date)
    phone = Column(String)
    telegram_nick = Column(String)
    notes = Column(Text)
    medical_book_expiry = Column(Date)
    is_helper = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    on_sick_leave = Column(Boolean, default=False)

    settings = relationship("EmployeeSetting", back_populates="employee")

    def _repr_(self):
        return f"<Employee(name={self.full_name})>"

class EmployeeSetting(Base):
    __tablename__ = "employee_settings"

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    is_allowed = Column(Boolean, default=True)
    is_preferred = Column(Boolean, default=False)

    employee = relationship("Employee", back_populates="settings")
    location = relationship("Location")

    def _repr_(self):
        return f"<EmployeeSetting(employee_id={self.employee_id}, location_id={self.location_id})>"
from sqlalchemy import Column, Integer, String, Date, Text
from datetime import date
from app.database import Base


class Log(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True)
    timestamp = Column(Date, default=date.today)
    action = Column(String)
    user = Column(String)
    details = Column(Text)
