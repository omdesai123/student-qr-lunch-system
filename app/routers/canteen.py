from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, desc

from app.database import get_db
from app.models import User, Student, Redemption
from app.schemas import (
    RedemptionScanRequest,
    RedemptionManualRequest,
    RedemptionResult
)
from app.security import require_staff
from app.qr_service import hash_qr_token
from app.utils.timezone import get_ist_now, get_ist_today, format_datetime_ist, format_time_ist

router = APIRouter(prefix="/api/canteen", tags=["Canteen Operations"], dependencies=[Depends(require_staff)])


def _process_redemption(student: Student, staff_username: str, db: Session) -> RedemptionResult:
    """
    Core atomic verification and redemption logic.
    Guarantees that each active student can redeem only once per calendar date.
    Safe against simultaneous concurrent scan attempts via database unique constraints.
    """
    today = get_ist_today()
    now = get_ist_now()

    # 1. Check student active status
    if not student.is_active:
        return RedemptionResult(
            success=False,
            status="INACTIVE_STUDENT",
            message=f"Student account '{student.student_id}' is deactivated. Lunch coupon not eligible.",
            student={
                "student_id": student.student_id,
                "name": student.name,
                "department": student.department,
                "year": student.year,
            }
        )

    # 2. Check if already redeemed today
    existing = (
        db.query(Redemption)
        .filter(Redemption.student_id == student.id, Redemption.redemption_date == today)
        .first()
    )
    if existing:
        return RedemptionResult(
            success=False,
            status="ALREADY_REDEEMED",
            message="ALREADY REDEEMED TODAY: Student has already claimed today's lunch coupon.",
            student={
                "student_id": student.student_id,
                "name": student.name,
                "department": student.department,
                "year": student.year,
            },
            redemption_time=format_time_ist(existing.redeemed_at),
            redemption_date=str(existing.redemption_date),
            redeemed_by=existing.redeemed_by,
        )

    # 3. Attempt atomic insert
    try:
        new_redemption = Redemption(
            student_id=student.id,
            redemption_date=today,
            redeemed_at=now,
            redeemed_by=staff_username,
        )
        db.add(new_redemption)
        db.commit()
        db.refresh(new_redemption)

        return RedemptionResult(
            success=True,
            status="APPROVED",
            message="LUNCH COUPON APPROVED! One lunch coupon successfully redeemed.",
            student={
                "student_id": student.student_id,
                "name": student.name,
                "department": student.department,
                "year": student.year,
            },
            redemption_time=format_time_ist(new_redemption.redeemed_at),
            redemption_date=str(new_redemption.redemption_date),
            redeemed_by=staff_username,
        )

    except IntegrityError:
        # Race condition caught: another scan succeeded simultaneously
        db.rollback()
        existing = (
            db.query(Redemption)
            .filter(Redemption.student_id == student.id, Redemption.redemption_date == today)
            .first()
        )
        return RedemptionResult(
            success=False,
            status="ALREADY_REDEEMED",
            message="DUPLICATE ATTEMPT DETECTED: This coupon was just claimed simultaneously.",
            student={
                "student_id": student.student_id,
                "name": student.name,
                "department": student.department,
                "year": student.year,
            },
            redemption_time=format_time_ist(existing.redeemed_at) if existing else "Just now",
            redemption_date=str(today),
            redeemed_by=existing.redeemed_by if existing else staff_username,
        )


@router.post("/redeem/scan", response_model=RedemptionResult)
def redeem_by_qr_scan(
    payload: RedemptionScanRequest,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db)
):
    """
    Validates a scanned QR token string, hashes it with SHA-256,
    locates the student record, and records redemption atomically.
    """
    token_str = payload.qr_token.strip()
    if not token_str:
        return RedemptionResult(
            success=False,
            status="INVALID_TOKEN",
            message="Empty QR code scan received. Please scan again.",
        )

    # Compute SHA-256 hash of the scanned token
    computed_hash = hash_qr_token(token_str)

    # Lookup student by stored hash
    student = db.query(Student).filter(Student.qr_token_hash == computed_hash).first()
    if not student:
        return RedemptionResult(
            success=False,
            status="INVALID_TOKEN",
            message="INVALID QR CODE: This coupon token is unrecognized or invalid.",
        )

    return _process_redemption(student, current_user.username, db)


@router.post("/redeem/manual", response_model=RedemptionResult)
def redeem_by_manual_id(
    payload: RedemptionManualRequest,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db)
):
    """
    Fallback manual redemption by Student ID when camera scan is not feasible.
    """
    clean_id = payload.student_id.strip()
    if not clean_id:
        return RedemptionResult(
            success=False,
            status="NOT_FOUND",
            message="Please provide a valid Student ID.",
        )

    student = db.query(Student).filter(func.lower(Student.student_id) == clean_id.lower()).first()
    if not student:
        return RedemptionResult(
            success=False,
            status="NOT_FOUND",
            message=f"Student ID '{clean_id}' was not found in the student directory.",
        )

    return _process_redemption(student, current_user.username, db)


@router.get("/stats")
def get_canteen_stats(db: Session = Depends(get_db)):
    """Returns today's total redemptions for the canteen live counter."""
    today = get_ist_today()
    total_today = db.query(Redemption).filter(Redemption.redemption_date == today).count()
    return {
        "date": today.strftime("%A, %d %B %Y"),
        "today_redemptions": total_today,
    }


@router.get("/recent")
def get_recent_redemptions(db: Session = Depends(get_db)):
    """Returns the last 20 successful redemptions made today."""
    today = get_ist_today()
    records = (
        db.query(Redemption)
        .join(Student, Redemption.student_id == Student.id)
        .filter(Redemption.redemption_date == today)
        .order_by(desc(Redemption.redeemed_at))
        .limit(20)
        .all()
    )

    items = []
    for r in records:
        items.append({
            "id": r.id,
            "student_id": r.student.student_id,
            "student_name": r.student.name,
            "department": r.student.department,
            "year": r.student.year,
            "redeemed_at": format_time_ist(r.redeemed_at),
            "redeemed_by": r.redeemed_by,
        })

    return {"recent": items}
