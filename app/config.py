import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "Student QR Lunch Coupon Management System"
    SECRET_KEY: str = "super-secret-secure-college-jwt-key-change-in-production-2026"
    QR_SECRET_SALT: str = "college-cryptographic-qr-salt-token-secure-hash-2026"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720  # 12 hours
    TIMEZONE: str = "Asia/Kolkata"
    DATABASE_URL: str = "sqlite:///./lunch_coupon.db"

    DEFAULT_ADMIN_USERNAME: str = "admin"
    DEFAULT_ADMIN_PASSWORD: str = "AdminPassword@2026"

    DEFAULT_STAFF_USERNAME: str = "canteen_staff"
    DEFAULT_STAFF_PASSWORD: str = "StaffPassword@2026"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
