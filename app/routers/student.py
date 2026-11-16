from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Student, Redemption
from app.security import require_student
from app.qr_service import derive_qr_token, generate_qr_image_bytes
from app.utils.timezone import get_ist_today, format_datetime_ist, format_time_ist

router = APIRouter(prefix="/api/student", tags=["Student Portal"], dependencies=[Depends(require_student)])


def _get_student_for_user(user: User, db: Session) -> Student:
    """Helper to locate the student profile for the authenticated student user."""
    student = None
    if user.student_record_id:
        student = db.query(Student).filter(Student.id == user.student_record_id).first()
    if not student:
        student = db.query(Student).filter(Student.student_id == user.username.upper()).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found for this account.",
        )
    return student


@router.get("/profile")
def get_student_profile(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    Returns student details, department, academic year, and today's lunch redemption status.
    Redemption status resets automatically each day at 00:00 IST.
    """
    student = _get_student_for_user(current_user, db)
    today = get_ist_today()

    redemption = (
        db.query(Redemption)
        .filter(Redemption.student_id == student.id, Redemption.redemption_date == today)
        .first()
    )

    return {
        "student_id": student.student_id,
        "name": student.name,
        "department": student.department,
        "year": student.year,
        "is_active": student.is_active,
        "today_date": today.strftime("%A, %d %B %Y"),
        "today_status": "REDEEMED" if redemption else "AVAILABLE",
        "redeemed_at": format_time_ist(redemption.redeemed_at) if redemption else None,
        "redeemed_by": redemption.redeemed_by if redemption else None,
    }


@router.get("/qr-image")
def get_personal_qr_image(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """Generates and serves the student's personal QR coupon image."""
    student = _get_student_for_user(current_user, db)
    token = derive_qr_token(student.student_id)
    img_bytes = generate_qr_image_bytes(token, student_id=student.student_id, student_name=student.name)

    return Response(
        content=img_bytes,
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=3600"}
    )


@router.get("/download-qr")
def download_personal_qr(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """Downloads personal QR coupon image as PNG."""
    student = _get_student_for_user(current_user, db)
    token = derive_qr_token(student.student_id)
    img_bytes = generate_qr_image_bytes(token, student_id=student.student_id, student_name=student.name)

    filename = f"QR_Lunch_Coupon_{student.student_id}.png"
    return Response(
        content=img_bytes,
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
