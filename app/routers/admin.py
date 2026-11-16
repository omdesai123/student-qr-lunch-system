import io
import csv
from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.database import get_db
from app.models import User, Student, Redemption
from app.schemas import (
    StudentCreate,
    StudentUpdate,
    StudentResponse,
    StudentDetail,
    DashboardStats,
    RedemptionLogItem,
    CSVImportSummary
)
from app.security import require_admin, hash_password
from app.qr_service import (
    derive_qr_token,
    hash_qr_token,
    generate_qr_image_bytes,
    generate_all_qr_zip
)
from app.utils.timezone import get_ist_today, format_datetime_ist, format_time_ist

router = APIRouter(prefix="/api/admin", tags=["Admin Operations"], dependencies=[Depends(require_admin)])


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Computes live stats: total students, active count, today's redemptions, remaining eligible."""
    today = get_ist_today()

    total_students = db.query(Student).count()
    active_students = db.query(Student).filter(Student.is_active == True).count()

    # Redemptions made today for active students
    redeemed_today = (
        db.query(Redemption)
        .join(Student, Redemption.student_id == Student.id)
        .filter(Redemption.redemption_date == today, Student.is_active == True)
        .count()
    )

    remaining_eligible = max(0, active_students - redeemed_today)
    redemption_pct = round((redeemed_today / active_students * 100), 1) if active_students > 0 else 0.0

    return DashboardStats(
        total_students=total_students,
        active_students=active_students,
        redeemed_today=redeemed_today,
        remaining_eligible_today=remaining_eligible,
        current_date=today.strftime("%A, %d %B %Y"),
        redemption_percentage=redemption_pct
    )


@router.get("/students")
def list_students(
    q: Optional[str] = Query(None, description="Search by ID or Name"),
    department: Optional[str] = Query(None, description="Filter by department"),
    year: Optional[int] = Query(None, description="Filter by year"),
    status: Optional[str] = Query(None, description="Filter: active / inactive"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Lists students with search, filters, pagination, and today's redemption status."""
    today = get_ist_today()
    query = db.query(Student)

    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter((Student.student_id.ilike(term)) | (Student.name.ilike(term)))

    if department and department.strip() and department != "all":
        query = query.filter(Student.department == department.strip())

    if year and year > 0:
        query = query.filter(Student.year == year)

    if status and status != "all":
        if status.lower() == "active":
            query = query.filter(Student.is_active == True)
        elif status.lower() == "inactive":
            query = query.filter(Student.is_active == False)

    total_count = query.count()
    offset = (page - 1) * limit
    students = query.order_by(Student.student_id.asc()).offset(offset).limit(limit).all()

    # Fetch today's redemptions for these students
    student_ids = [s.id for s in students]
    redemptions = (
        db.query(Redemption)
        .filter(Redemption.student_id.in_(student_ids), Redemption.redemption_date == today)
        .all()
    )
    redemption_map = {r.student_id: r for r in redemptions}

    items = []
    for s in students:
        red = redemption_map.get(s.id)
        items.append({
            "id": s.id,
            "student_id": s.student_id,
            "name": s.name,
            "department": s.department,
            "year": s.year,
            "is_active": s.is_active,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "today_status": "REDEEMED" if red else "AVAILABLE",
            "redeemed_at_str": format_time_ist(red.redeemed_at) if red else None,
            "redeemed_by": red.redeemed_by if red else None,
        })

    return {
        "items": items,
        "total": total_count,
        "page": page,
        "limit": limit,
        "total_pages": (total_count + limit - 1) // limit if limit else 1
    }


@router.post("/students", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
def create_student(payload: StudentCreate, db: Session = Depends(get_db)):
    """Creates a new student, generates QR token hash, and sets up login account."""
    clean_id = payload.student_id.strip().upper()

    existing = db.query(Student).filter(Student.student_id == clean_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Student ID '{clean_id}' already exists in system.",
        )

    # Derive permanent QR token and hash
    token = derive_qr_token(clean_id)
    token_hash = hash_qr_token(token)

    new_student = Student(
        student_id=clean_id,
        name=payload.name.strip(),
        department=payload.department.strip(),
        year=payload.year,
        qr_token_hash=token_hash,
        is_active=payload.is_active,
    )
    db.add(new_student)
    db.flush()

    # Create associated student user login account
    login_password = payload.password if payload.password else clean_id
    existing_user = db.query(User).filter(User.username == clean_id).first()
    if not existing_user:
        new_user = User(
            username=clean_id,
            password_hash=hash_password(login_password),
            role="student",
            is_active=payload.is_active,
            student_record_id=new_student.id,
        )
        db.add(new_user)
    else:
        existing_user.student_record_id = new_student.id
        existing_user.is_active = payload.is_active

    db.commit()
    db.refresh(new_student)
    return new_student


@router.get("/students/{id}", response_model=StudentDetail)
def get_student(id: int, db: Session = Depends(get_db)):
    """Retrieves a single student with redemption history details."""
    student = db.query(Student).filter(Student.id == id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

    today = get_ist_today()
    red = (
        db.query(Redemption)
        .filter(Redemption.student_id == student.id, Redemption.redemption_date == today)
        .first()
    )

    return StudentDetail(
        id=student.id,
        student_id=student.student_id,
        name=student.name,
        department=student.department,
        year=student.year,
        is_active=student.is_active,
        created_at=student.created_at,
        today_status="REDEEMED" if red else "AVAILABLE",
        redeemed_at_str=format_datetime_ist(red.redeemed_at) if red else None,
        redeemed_by=red.redeemed_by if red else None,
    )


@router.put("/students/{id}", response_model=StudentResponse)
def update_student(id: int, payload: StudentUpdate, db: Session = Depends(get_db)):
    """Updates student information and active status."""
    student = db.query(Student).filter(Student.id == id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

    if payload.name is not None:
        student.name = payload.name.strip()
    if payload.department is not None:
        student.department = payload.department.strip()
    if payload.year is not None:
        student.year = payload.year
    if payload.is_active is not None:
        student.is_active = payload.is_active
        # Also sync user active status
        user = db.query(User).filter(User.student_record_id == student.id).first()
        if user:
            user.is_active = payload.is_active

    if payload.password:
        user = db.query(User).filter(User.student_record_id == student.id).first()
        if user:
            user.password_hash = hash_password(payload.password)

    db.commit()
    db.refresh(student)
    return student


@router.post("/students/{id}/toggle-status")
def toggle_student_status(id: int, db: Session = Depends(get_db)):
    """Toggles student active/inactive status."""
    student = db.query(Student).filter(Student.id == id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

    student.is_active = not student.is_active
    user = db.query(User).filter(User.student_record_id == student.id).first()
    if user:
        user.is_active = student.is_active

    db.commit()
    return {"id": student.id, "student_id": student.student_id, "is_active": student.is_active}


@router.delete("/students/{id}", status_code=status.HTTP_200_OK)
def delete_student(id: int, db: Session = Depends(get_db)):
    """Deletes a student, their redemptions, and linked user account."""
    student = db.query(Student).filter(Student.id == id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

    stu_id = student.student_id
    # Remove user account
    db.query(User).filter(User.student_record_id == student.id).delete()
    # Remove student (redemptions cascade)
    db.delete(student)
    db.commit()
    return {"message": f"Student {stu_id} and all related records have been deleted."}


@router.post("/import-csv", response_model=CSVImportSummary)
def import_students_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Imports students in bulk from a CSV file.
    Expected CSV columns: student_id, name, department, year (optional: password, is_active)
    """
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Please upload a .csv file.",
        )

    content = file.file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = content.decode("latin-1")
        except Exception:
            raise HTTPException(status_code=400, detail="Unable to parse CSV file encoding.")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV file appears to be empty.")

    # Normalize fieldnames to lowercase stripped
    field_map = {f.strip().lower(): f for f in reader.fieldnames}
    required = ["student_id", "name", "department", "year"]
    for req in required:
        if req not in field_map:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required CSV column '{req}'. Found columns: {list(reader.fieldnames)}"
            )

    # Pre-fetch existing student IDs and usernames in one query for instant deduplication
    existing_stu_ids = {s[0] for s in db.query(Student.student_id).all()}
    existing_usernames = {u[0] for u in db.query(User.username).all()}

    imported = 0
    skipped = 0
    errors = []
    total = 0
    pwd_cache = {}

    students_to_add = []
    users_to_add = []

    for row_num, raw_row in enumerate(reader, start=2):
        total += 1
        row = {k.strip().lower(): v.strip() for k, v in raw_row.items() if k}
        stu_id = row.get("student_id", "").strip().upper()
        name = row.get("name", "").strip()
        dept = row.get("department", "").strip()
        year_str = row.get("year", "").strip()
        pwd = row.get("password", "").strip()
        is_active_val = row.get("is_active", "true").strip().lower() in ("true", "1", "yes", "active")

        if not stu_id or not name or not dept or not year_str:
            errors.append(f"Row {row_num}: Missing required field values.")
            continue

        try:
            year = int(year_str)
            if year < 1 or year > 8:
                year = 1
        except ValueError:
            year = 1

        # Check existing student in set
        if stu_id in existing_stu_ids:
            skipped += 1
            continue

        token = derive_qr_token(stu_id)
        token_hash = hash_qr_token(token)

        student = Student(
            student_id=stu_id,
            name=name,
            department=dept,
            year=year,
            qr_token_hash=token_hash,
            is_active=is_active_val,
        )
        students_to_add.append(student)
        existing_stu_ids.add(stu_id)

        # Hash password (with cache for identical passwords)
        initial_pwd = pwd if pwd else stu_id
        if initial_pwd not in pwd_cache:
            pwd_cache[initial_pwd] = hash_password(initial_pwd)
        hashed_pwd = pwd_cache[initial_pwd]

        if stu_id not in existing_usernames:
            user = User(
                username=stu_id,
                password_hash=hashed_pwd,
                role="student",
                is_active=is_active_val,
            )
            users_to_add.append(user)
            existing_usernames.add(stu_id)

        imported += 1

    # Bulk add and commit in one transaction
    db.add_all(students_to_add)
    db.flush()

    for s, u in zip(students_to_add, users_to_add):
        u.student_record_id = s.id

    db.add_all(users_to_add)
    db.commit()

    return CSVImportSummary(
        total_rows=total,
        imported=imported,
        skipped_duplicates=skipped,
        errors=errors[:20]
    )


@router.get("/download-sample-csv")
def download_sample_csv():
    """Generates a sample CSV template for administrative import."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["student_id", "name", "department", "year", "password", "is_active"])
    writer.writerow(["STU2026001", "Aarav Sharma", "Computer Science", 2, "Pass@123", "true"])
    writer.writerow(["STU2026002", "Diya Patel", "Information Technology", 3, "Pass@123", "true"])
    writer.writerow(["STU2026003", "Rohan Mehta", "Mechanical Engineering", 1, "Pass@123", "true"])
    writer.writerow(["STU2026004", "Ananya Iyer", "Electronics & Comm", 4, "Pass@123", "true"])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sample_students_template.csv"}
    )


@router.get("/qr/{student_id}")
def download_single_qr(student_id: str, db: Session = Depends(get_db)):
    """Generates and serves an individual student's QR code coupon as PNG."""
    clean_id = student_id.strip().upper()
    student = db.query(Student).filter(Student.student_id == clean_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    token = derive_qr_token(clean_id)
    img_bytes = generate_qr_image_bytes(token, student_id=student.student_id, student_name=student.name)

    return Response(
        content=img_bytes,
        media_type="image/png",
        headers={"Content-Disposition": f'inline; filename="QR_{clean_id}.png"'}
    )


@router.get("/qr-zip")
def download_all_qr_zip(db: Session = Depends(get_db)):
    """Bundles all active students' QR coupons into a downloadable ZIP archive."""
    students = (
        db.query(Student.student_id, Student.name, Student.department)
        .filter(Student.is_active == True)
        .order_by(Student.student_id.asc())
        .all()
    )

    if not students:
        raise HTTPException(status_code=400, detail="No active students found to generate QR codes.")

    zip_bytes = generate_all_qr_zip([(s[0], s[1], s[2]) for s in students])

    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=all_student_qr_coupons.zip"}
    )


@router.get("/redemptions")
def get_redemptions(
    redemption_date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
    q: Optional[str] = Query(None, description="Search by student ID or name"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Lists redemption history with student details, staff name, and exact timestamp."""
    target_date = get_ist_today()
    if redemption_date:
        try:
            target_date = date.fromisoformat(redemption_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Expected YYYY-MM-DD.")

    query = (
        db.query(Redemption)
        .join(Student, Redemption.student_id == Student.id)
        .filter(Redemption.redemption_date == target_date)
    )

    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter((Student.student_id.ilike(term)) | (Student.name.ilike(term)))

    total_count = query.count()
    records = (
        query.order_by(desc(Redemption.redeemed_at))
        .offset((page - 1) * limit)
        .limit(limit)
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
            "redemption_date": str(r.redemption_date),
            "redeemed_at": format_datetime_ist(r.redeemed_at),
            "redeemed_by": r.redeemed_by,
        })

    return {
        "items": items,
        "total": total_count,
        "page": page,
        "limit": limit,
        "total_pages": (total_count + limit - 1) // limit if limit else 1,
        "date": str(target_date),
    }


@router.get("/export-redemptions-csv")
def export_redemptions_csv(
    redemption_date: Optional[str] = Query(None, description="Date in YYYY-MM-DD or 'all'"),
    db: Session = Depends(get_db)
):
    """Exports daily redemption report as a CSV file."""
    query = (
        db.query(Redemption)
        .join(Student, Redemption.student_id == Student.id)
    )

    filename_date = "all"
    if redemption_date and redemption_date.lower() != "all":
        try:
            target_date = date.fromisoformat(redemption_date)
            query = query.filter(Redemption.redemption_date == target_date)
            filename_date = str(target_date)
        except ValueError:
            target_date = get_ist_today()
            query = query.filter(Redemption.redemption_date == target_date)
            filename_date = str(target_date)
    elif not redemption_date:
        target_date = get_ist_today()
        query = query.filter(Redemption.redemption_date == target_date)
        filename_date = str(target_date)

    records = query.order_by(desc(Redemption.redeemed_at)).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Redemption ID",
        "Student ID",
        "Student Name",
        "Department",
        "Academic Year",
        "Redemption Date (IST)",
        "Redeemed Timestamp (IST)",
        "Verified By (Staff)"
    ])

    for r in records:
        writer.writerow([
            r.id,
            r.student.student_id,
            r.student.name,
            r.student.department,
            f"Year {r.student.year}",
            str(r.redemption_date),
            format_datetime_ist(r.redeemed_at),
            r.redeemed_by
        ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=lunch_redemptions_{filename_date}.csv"}
    )
