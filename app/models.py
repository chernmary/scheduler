from sqlalchemy import Column, Integer, String, Boolean, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False, unique=True)
    birth_date = Column(Date, nullable=True)
    phone = Column(String, nullable=True)
    telegram_username = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    med_book_expiry = Column(Date, nullable=True)
    is_helper = Column(Boolean, default=False, nullable=False)
    on_sick_leave = Column(Boolean, default=False, nullable=False)

    settings = relationship("EmployeeSetting", back_populates="employee", cascade="all, delete-orphan")
    shifts = relationship("Shift", back_populates="employee")


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    order = Column(Integer, nullable=False, default=0)
    zone = Column(String, nullable=True)

    settings = relationship("EmployeeSetting", back_populates="location", cascade="all, delete-orphan")
    shifts = relationship("Shift", back_populates="location")


class EmployeeSetting(Base):
    __tablename__ = "employee_settings"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id", ondelete="CASCADE"), nullable=False)
    is_allowed = Column(Boolean, default=True, nullable=False)
    is_preferred = Column(Boolean, default=False, nullable=False)

    employee = relationship("Employee", back_populates="settings")
    location = relationship("Location", back_populates="settings")

    __table_args__ = (
        UniqueConstraint("employee_id", "location_id", name="uix_employee_location"),
    )


class Shift(Base):
    __tablename__ = "shifts"

    STATUS_DRAFT = "draft"
    STATUS_PUBLISHED = "published"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id", ondelete="CASCADE"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(20), nullable=False, default=STATUS_DRAFT)

    location = relationship("Location", back_populates="shifts")
    employee = relationship("Employee", back_populates="shifts")

    __table_args__ = (
        UniqueConstraint(
            "date",
            "location_id",
            "status",
            name="uix_date_location_status",
        ),
    )
