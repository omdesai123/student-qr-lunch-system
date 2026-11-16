"""
Comprehensive Test Suite for Student QR Lunch Coupon Management System
Covers Authentication, Role-based Access, Cryptographic QR Tokens,
Daily Redemption Workflow, Duplicate Scans, Inactive Accounts, and Concurrency.
"""

import sys
import os
import unittest
import threading
from datetime import datetime, date
from concurrent.futures import ThreadPoolExecutor

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import IntegrityError
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.config import settings
from app.models import User, Student, Redemption
from app.security import hash_password, create_access_token
from app.qr_service import derive_qr_token, hash_qr_token, generate_qr_image_bytes, generate_all_qr_zip
from app.utils.timezone import get_ist_today, get_ist_now
from main import app

# File-based SQLite for realistic multi-connection concurrency testing
TEST_DB_FILE = "./test_lunch.db"
if os.path.exists(TEST_DB_FILE):
    try:
        os.remove(TEST_DB_FILE)
    except Exception:
        pass

test_engine = create_engine(
    f"sqlite:///{TEST_DB_FILE}",
    connect_args={"check_same_thread": False, "timeout": 20}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


class TestLunchCouponSystem(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=test_engine)
        cls.db = TestingSessionLocal()

        # Seed Test Admin
        cls.admin_user = User(
            username="test_admin",
            password_hash=hash_password("AdminPass123!"),
            role="admin",
            is_active=True
        )
        cls.db.add(cls.admin_user)

        # Seed Test Staff
        cls.staff_user = User(
            username="test_staff",
            password_hash=hash_password("StaffPass123!"),
            role="staff",
            is_active=True
        )
        cls.db.add(cls.staff_user)

        # Seed Active Test Student 1
        t1 = derive_qr_token("TEST001")
        cls.student1 = Student(
            student_id="TEST001",
            name="Alice Test",
            department="Computer Science",
            year=2,
            qr_token_hash=hash_qr_token(t1),
            is_active=True
        )
        cls.db.add(cls.student1)
        cls.db.flush()

        cls.student1_user = User(
            username="TEST001",
            password_hash=hash_password("TEST001"),
            role="student",
            is_active=True,
            student_record_id=cls.student1.id
        )
        cls.db.add(cls.student1_user)

        # Seed Active Test Student 2
        t2 = derive_qr_token("TEST002")
        cls.student2 = Student(
            student_id="TEST002",
            name="Bob Test",
            department="Information Technology",
            year=3,
            qr_token_hash=hash_qr_token(t2),
            is_active=True
        )
        cls.db.add(cls.student2)
        cls.db.flush()

        cls.student2_user = User(
            username="TEST002",
            password_hash=hash_password("TEST002"),
            role="student",
            is_active=True,
            student_record_id=cls.student2.id
        )
        cls.db.add(cls.student2_user)

        # Seed Deactivated Test Student 3
        t3 = derive_qr_token("TEST003")
        cls.student3 = Student(
            student_id="TEST003",
            name="Inactive Charlie",
            department="Mechanical Engineering",
            year=1,
            qr_token_hash=hash_qr_token(t3),
            is_active=False
        )
        cls.db.add(cls.student3)
        cls.db.flush()

        cls.student3_user = User(
            username="TEST003",
            password_hash=hash_password("TEST003"),
            role="student",
            is_active=False,
            student_record_id=cls.student3.id
        )
        cls.db.add(cls.student3_user)

        cls.db.commit()

        # Generate auth tokens
        cls.admin_token = create_access_token({"sub": "test_admin", "role": "admin", "uid": cls.admin_user.id})
        cls.staff_token = create_access_token({"sub": "test_staff", "role": "staff", "uid": cls.staff_user.id})
        cls.student1_token = create_access_token({"sub": "TEST001", "role": "student", "uid": cls.student1_user.id})

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        test_engine.dispose()
        if os.path.exists(TEST_DB_FILE):
            try:
                os.remove(TEST_DB_FILE)
            except Exception:
                pass

    # 1. Test Authentication
    def test_01_login_success(self):
        res = client.post("/api/auth/login", json={"username": "test_admin", "password": "AdminPass123!"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["user"]["role"], "admin")

    def test_02_login_invalid_password(self):
        res = client.post("/api/auth/login", json={"username": "test_admin", "password": "WrongPassword"})
        self.assertEqual(res.status_code, 401)

    def test_03_login_inactive_user(self):
        res = client.post("/api/auth/login", json={"username": "TEST003", "password": "TEST003"})
        self.assertEqual(res.status_code, 403)

    # 2. Cryptographic QR Token Properties
    def test_04_qr_token_properties(self):
        token = derive_qr_token("TEST001")
        self.assertEqual(len(token), 64)
        self.assertNotIn("TEST001", token)  # Does not contain predictable ID

        token_hash = hash_qr_token(token)
        self.assertEqual(len(token_hash), 64)

        # Image generation test
        img_bytes = generate_qr_image_bytes(token, "TEST001", "Alice Test")
        self.assertTrue(len(img_bytes) > 1000)
        self.assertEqual(img_bytes[:8], b"\x89PNG\r\n\x1a\n")

    # 3. Canteen QR Scanner & Daily Redemption Workflow
    def test_05_canteen_qr_redemption_approved(self):
        token = derive_qr_token("TEST001")
        headers = {"Authorization": f"Bearer {self.staff_token}"}
        res = client.post("/api/canteen/redeem/scan", json={"qr_token": token}, headers=headers)

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["status"], "APPROVED")
        self.assertEqual(data["student"]["student_id"], "TEST001")
        self.assertIsNotNone(data["redemption_time"])

    def test_06_canteen_duplicate_redemption_rejected(self):
        # Attempting to scan the same QR token again on the same day
        token = derive_qr_token("TEST001")
        headers = {"Authorization": f"Bearer {self.staff_token}"}
        res = client.post("/api/canteen/redeem/scan", json={"qr_token": token}, headers=headers)

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["status"], "ALREADY_REDEEMED")
        self.assertIn("ALREADY REDEEMED TODAY", data["message"])

    def test_07_canteen_invalid_qr_rejected(self):
        headers = {"Authorization": f"Bearer {self.staff_token}"}
        res = client.post("/api/canteen/redeem/scan", json={"qr_token": "random_fake_unauthorized_token_xyz"}, headers=headers)

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["status"], "INVALID_TOKEN")

    def test_08_canteen_inactive_student_rejected(self):
        token = derive_qr_token("TEST003")
        headers = {"Authorization": f"Bearer {self.staff_token}"}
        res = client.post("/api/canteen/redeem/scan", json={"qr_token": token}, headers=headers)

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["status"], "INACTIVE_STUDENT")

    def test_09_manual_student_id_redemption(self):
        # Student 2 has not redeemed today yet
        headers = {"Authorization": f"Bearer {self.staff_token}"}
        res = client.post("/api/canteen/redeem/manual", json={"student_id": "TEST002"}, headers=headers)

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["status"], "APPROVED")
        self.assertEqual(data["student"]["student_id"], "TEST002")

        # Second manual attempt should be rejected
        res2 = client.post("/api/canteen/redeem/manual", json={"student_id": "TEST002"}, headers=headers)
        data2 = res2.json()
        self.assertFalse(data2["success"])
        self.assertEqual(data2["status"], "ALREADY_REDEEMED")

    # 4. Atomic Concurrency & Database-Level Unique Constraint
    def test_10_concurrent_simultaneous_redemptions(self):
        # Create a fresh student for race condition testing
        t_conc = derive_qr_token("CONC001")
        stu_conc = Student(
            student_id="CONC001",
            name="Concurrency Test Student",
            department="Computer Science",
            year=4,
            qr_token_hash=hash_qr_token(t_conc),
            is_active=True,
            created_at=get_ist_now()
        )
        self.db.add(stu_conc)
        self.db.commit()

        headers = {"Authorization": f"Bearer {self.staff_token}"}
        results = []

        def attempt_scan():
            res = client.post("/api/canteen/redeem/scan", json={"qr_token": t_conc}, headers=headers)
            results.append(res.json())

        # Fire 10 threads simultaneously
        threads = [threading.Thread(target=attempt_scan) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        approved_count = sum(1 for r in results if r.get("status") == "APPROVED")
        already_redeemed_count = sum(1 for r in results if r.get("status") == "ALREADY_REDEEMED")

        # Exactly 1 scan must be APPROVED, remaining 9 must be ALREADY_REDEEMED
        self.assertEqual(approved_count, 1)
        self.assertEqual(already_redeemed_count, 9)

    # 5. Student Dashboard
    def test_11_student_profile_status(self):
        # Alice redeemed earlier in test_05, so her status should be REDEEMED
        headers = {"Authorization": f"Bearer {self.student1_token}"}
        res = client.get("/api/student/profile", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["student_id"], "TEST001")
        self.assertEqual(data["today_status"], "REDEEMED")
        self.assertIsNotNone(data["redeemed_at"])

    # 6. Admin Analytics, Search, and Export
    def test_12_admin_stats(self):
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        res = client.get("/api/admin/stats", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["total_students"] >= 3)
        self.assertTrue(data["redeemed_today"] >= 2)

    def test_13_admin_student_search_and_filter(self):
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        res = client.get("/api/admin/students?q=Alice", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["student_id"], "TEST001")

    def test_14_admin_qr_zip_bundle(self):
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        res = client.get("/api/admin/qr-zip", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers["content-type"], "application/zip")
        self.assertTrue(len(res.content) > 5000)

    def test_15_admin_redemptions_export_csv(self):
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        res = client.get("/api/admin/export-redemptions-csv", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers["content-type"], "text/csv; charset=utf-8")
        self.assertIn("Redemption ID", res.text)
        self.assertIn("TEST001", res.text)


if __name__ == "__main__":
    unittest.main()
