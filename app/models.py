from sqlalchemy import Column, Integer, String, Date, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, unique=True, index=True)
    birth_date = Column(Date, nullable=True)
    phone = Column(String, nullable=True)
    telegram_username = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    medical_book_expiry = Column(Date, nullable=True)
    on_sick_leave = Column(Boolean, default=False)
    is_helper = Column(Boolean, default=False)

    settings = relationship("EmployeeSetting", back_populates="employee")
    shifts = relationship("Shift", back_populates="employee")


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    order = Column(Integer)
    zone = Column(String)  # например, main_building, multpark, aviapark, lunosik

    settings = relationship("EmployeeSetting", back_populates="location")
    shifts = relationship("Shift", back_populates="location")


class EmployeeSetting(Base):
    __tablename__ = "employee_settings"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"))
    location_id = Column(Integer, ForeignKey("locations.id"))
    is_allowed = Column(Boolean, default=True)
    is_preferred = Column(Boolean, default=False)

    employee = relationship("Employee", back_populates="settings")
    location = relationship("Location", back_populates="settings")


class Shift(Base):
    __tablename__ = "shifts"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, index=True)
    location_id = Column(Integer, ForeignKey("locations.id"))
    employee_id = Column(Integer, ForeignKey("employees.id"))
    status = Column(String, default="draft")  # draft | published | archived

    location = relationship("Location", back_populates="shifts")
    employee = relationship("Employee", back_populates="shifts")
