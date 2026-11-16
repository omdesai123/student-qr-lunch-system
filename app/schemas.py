from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date


# ================= Authentication Schemas =================
class LoginRequest(BaseModel):
    username: str = Field(..., description="Username or Student ID")
    password: str = Field(..., description="Account Password")


class UserInfo(BaseModel):
    id: int
    username: str
    role: str  # "admin", "staff", "student"
    name: Optional[str] = None
    student_id: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo


# ================= Student Schemas =================
class StudentBase(BaseModel):
    student_id: str
    name: str
    department: str
    year: int = Field(..., ge=1, le=8)
    is_active: bool = True


class StudentCreate(StudentBase):
    password: Optional[str] = None  # If not provided, defaults to student_id


class StudentUpdate(BaseModel):
    name: Optional[str] = None
    department: Optional[str] = None
    year: Optional[int] = Field(None, ge=1, le=8)
    is_active: Optional[bool] = None
    password: Optional[str] = None


class StudentResponse(StudentBase):
    id: int
    created_at: datetime
    # Note: qr_token_hash is NEVER exposed to client

    class Config:
        from_attributes = True


class StudentDetail(StudentResponse):
    today_status: str  # "AVAILABLE" or "REDEEMED"
    redeemed_at_str: Optional[str] = None
    redeemed_by: Optional[str] = None


# ================= Redemption Schemas =================
class RedemptionScanRequest(BaseModel):
    qr_token: str = Field(..., description="Scanned QR token string")


class RedemptionManualRequest(BaseModel):
    student_id: str = Field(..., description="Student ID for manual fallback")


class RedemptionResult(BaseModel):
    success: bool
    status: str  # "APPROVED", "ALREADY_REDEEMED", "INVALID_TOKEN", "INACTIVE_STUDENT", "NOT_FOUND"
    message: str
    student: Optional[dict] = None
    redemption_time: Optional[str] = None
    redemption_date: Optional[str] = None
    redeemed_by: Optional[str] = None


class RedemptionLogItem(BaseModel):
    id: int
    student_id: str
    student_name: str
    department: str
    year: int
    redemption_date: str
    redeemed_at: str
    redeemed_by: str


# ================= Dashboard & Reports =================
class DashboardStats(BaseModel):
    total_students: int
    active_students: int
    redeemed_today: int
    remaining_eligible_today: int
    current_date: str
    redemption_percentage: float


class CSVImportSummary(BaseModel):
    total_rows: int
    imported: int
    skipped_duplicates: int
    errors: List[str] = []
