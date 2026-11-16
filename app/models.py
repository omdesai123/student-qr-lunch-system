from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index
)
from sqlalchemy.orm import relationship
from app.database import Base
from app.utils.timezone import get_ist_now


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)  # "admin", "staff", "student"
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=get_ist_now, nullable=False)

    # Optional reference to link student user account with student record
    student_record_id = Column(Integer, ForeignKey("students.id", ondelete="SET NULL"), nullable=True)
    student_profile = relationship("Student", back_populates="user_account", foreign_keys=[student_record_id])

    def __repr__(self):
        return f"<User username={self.username} role={self.role}>"


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String(30), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    department = Column(String(50), nullable=False)
    year = Column(Integer, nullable=False)  # Academic year: 1, 2, 3, 4
    qr_token_hash = Column(String(64), unique=True, index=True, nullable=False)  # SHA-256 hex string
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=get_ist_now, nullable=False)

    # Relationships
    user_account = relationship("User", back_populates="student_profile", uselist=False)
    redemptions = relationship("Redemption", back_populates="student", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Student id={self.student_id} name={self.name} dept={self.department}>"


class Redemption(Base):
    __tablename__ = "redemptions"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    redemption_date = Column(Date, nullable=False, index=True)
    redeemed_at = Column(DateTime, nullable=False, default=get_ist_now)
    redeemed_by = Column(String(50), nullable=False)  # Staff username

    # Relationship
    student = relationship("Student", back_populates="redemptions")

    # Business rule: Database-level unique constraint to strictly enforce 1 lunch per day per student
    __table_args__ = (
        UniqueConstraint("student_id", "redemption_date", name="uq_student_daily_redemption"),
        Index("idx_student_date", "student_id", "redemption_date"),
    )

    def __repr__(self):
        return f"<Redemption student_id={self.student_id} date={self.redemption_date} at={self.redeemed_at}>"
