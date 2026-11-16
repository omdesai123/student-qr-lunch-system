from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import User, Student
from app.schemas import LoginRequest, TokenResponse, UserInfo
from app.security import (
    verify_password,
    create_access_token,
    get_current_user
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    """
    Unified authentication endpoint for Admin, Canteen Staff, and Students.
    Sets an HTTP-only cookie and returns a Bearer JWT.
    """
    clean_username = payload.username.strip()
    user = db.query(User).filter(func.lower(User.username) == clean_username.lower()).first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is currently inactive. Please contact administration.",
        )

    # Resolve student profile info if student user
    student_name = None
    student_id = None
    if user.role == "student":
        student = db.query(Student).filter(Student.user_account.has(id=user.id)).first()
        if not student:
            # Fallback by student_id == username
            student = db.query(Student).filter(func.lower(Student.student_id) == clean_username.lower()).first()
        if student:
            student_name = student.name
            student_id = student.student_id
            if not student.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Your student profile is deactivated. Please contact the college office.",
                )

    # Issue JWT token
    token_claims = {
        "sub": user.username,
        "role": user.role,
        "uid": user.id,
    }
    if student_id:
        token_claims["student_id"] = student_id

    access_token = create_access_token(token_claims)

    # Set cookie for page navigation in browser
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        samesite="lax",
        max_age=12 * 3600,
        path="/"
    )

    user_info = UserInfo(
        id=user.id,
        username=user.username,
        role=user.role,
        name=student_name if student_name else user.username.capitalize(),
        student_id=student_id,
        is_active=user.is_active,
    )

    return TokenResponse(access_token=access_token, token_type="bearer", user=user_info)


@router.post("/logout")
def logout(response: Response):
    """Logs out user by clearing the authentication cookie."""
    response.delete_cookie(key="access_token", path="/")
    return {"message": "Logged out successfully."}


@router.get("/me", response_model=UserInfo)
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Returns the authenticated user's profile and credentials."""
    student_name = None
    student_id = None
    if current_user.role == "student":
        student = db.query(Student).filter(Student.user_account.has(id=current_user.id)).first()
        if not student:
            student = db.query(Student).filter(func.lower(Student.student_id) == current_user.username.lower()).first()
        if student:
            student_name = student.name
            student_id = student.student_id

    return UserInfo(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        name=student_name if student_name else current_user.username.capitalize(),
        student_id=student_id,
        is_active=current_user.is_active,
    )
