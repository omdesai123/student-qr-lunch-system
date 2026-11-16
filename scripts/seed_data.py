"""
Database Seeding Script
Bootstraps initial Administrator, Canteen Staff, and Sample Students.
"""

import sys
import csv
import os

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session
from app.database import init_db, SessionLocal
from app.models import User, Student
from app.security import hash_password
from app.qr_service import derive_qr_token, hash_qr_token
from app.config import settings


def seed_database(limit_students: int = 50):
    print("Initializing database tables...")
    init_db()

    db: Session = SessionLocal()
    try:
        # 1. Seed Administrator
        admin = db.query(User).filter(User.username == settings.DEFAULT_ADMIN_USERNAME).first()
        if not admin:
            admin = User(
                username=settings.DEFAULT_ADMIN_USERNAME,
                password_hash=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
                role="admin",
                is_active=True,
            )
            db.add(admin)
            print(f"Created default Admin user: {settings.DEFAULT_ADMIN_USERNAME}")
        else:
            print(f"Admin user '{settings.DEFAULT_ADMIN_USERNAME}' already exists.")

        # 2. Seed Canteen Staff
        staff = db.query(User).filter(User.username == settings.DEFAULT_STAFF_USERNAME).first()
        if not staff:
            staff = User(
                username=settings.DEFAULT_STAFF_USERNAME,
                password_hash=hash_password(settings.DEFAULT_STAFF_PASSWORD),
                role="staff",
                is_active=True,
            )
            db.add(staff)
            print(f"Created default Staff user: {settings.DEFAULT_STAFF_USERNAME}")
        else:
            print(f"Staff user '{settings.DEFAULT_STAFF_USERNAME}' already exists.")

        db.commit()

        # 3. Seed Students from sample_500_students.csv
        csv_path = "sample_500_students.csv"
        if not os.path.exists(csv_path):
            from scripts.generate_sample_csv import generate_500_students_csv
            generate_500_students_csv(csv_path)

        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            count = 0
            # Common default password hash for faster seeding
            default_password_hash = hash_password("Pass@123")

            for row in reader:
                if limit_students and count >= limit_students:
                    break

                stu_id = row["student_id"].strip().upper()
                existing = db.query(Student).filter(Student.student_id == stu_id).first()
                if existing:
                    continue

                token = derive_qr_token(stu_id)
                token_hash = hash_qr_token(token)
                is_act = row["is_active"].strip().lower() in ("true", "1", "yes")

                student = Student(
                    student_id=stu_id,
                    name=row["name"].strip(),
                    department=row["department"].strip(),
                    year=int(row["year"]),
                    qr_token_hash=token_hash,
                    is_active=is_act,
                )
                db.add(student)
                db.flush()

                # Student user account (password can be stu_id or Pass@123)
                user = User(
                    username=stu_id,
                    password_hash=hash_password(stu_id),
                    role="student",
                    is_active=is_act,
                    student_record_id=student.id,
                )
                db.add(user)
                count += 1

            db.commit()
            print(f"Successfully seeded {count} sample students into database.")

    finally:
        db.close()


if __name__ == "__main__":
    limit = 50
    if "--all" in sys.argv:
        limit = 500
    seed_database(limit_students=limit)
