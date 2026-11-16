import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.config import settings
from app.database import init_db, get_db
from app.models import User, Student
from app.security import hash_password, decode_access_token
from app.routers.auth import router as auth_router
from app.routers.admin import router as admin_router
from app.routers.student import router as student_router
from app.routers.canteen import router as canteen_router


def seed_initial_admin_and_staff(db: Session):
    """Bootstraps default administrator and canteen staff accounts if missing."""
    # Seed Admin
    admin_user = db.query(User).filter(User.username == settings.DEFAULT_ADMIN_USERNAME).first()
    if not admin_user:
        admin_user = User(
            username=settings.DEFAULT_ADMIN_USERNAME,
            password_hash=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
            role="admin",
            is_active=True,
        )
        db.add(admin_user)

    # Seed Staff
    staff_user = db.query(User).filter(User.username == settings.DEFAULT_STAFF_USERNAME).first()
    if not staff_user:
        staff_user = User(
            username=settings.DEFAULT_STAFF_USERNAME,
            password_hash=hash_password(settings.DEFAULT_STAFF_PASSWORD),
            role="staff",
            is_active=True,
        )
        db.add(staff_user)

    db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure tables exist and seed initial credentials
    init_db()
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        seed_initial_admin_and_staff(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="Digital Lunch Coupon Management System for Colleges with Cryptographic QR Verification",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration for flexibility across local devices & mobile testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static assets
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Register API routers
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(student_router)
app.include_router(canteen_router)


# ================= Frontend Web Page Routes =================

def _get_user_from_cookie(request: Request, db: Session):
    cookie_token = request.cookies.get("access_token")
    if not cookie_token:
        return None
    token = cookie_token.replace("Bearer ", "").strip()
    payload = decode_access_token(token)
    if not payload:
        return None
    username = payload.get("sub")
    if not username:
        return None
    return db.query(User).filter(User.username == username, User.is_active == True).first()


@app.get("/", response_class=HTMLResponse)
def index_page(request: Request, db: Session = Depends(get_db)):
    """Landing route: redirects authenticated user to their role dashboard, or to login."""
    user = _get_user_from_cookie(request, db)
    if user:
        if user.role == "admin":
            return RedirectResponse(url="/admin")
        elif user.role == "staff":
            return RedirectResponse(url="/canteen")
        elif user.role == "student":
            return RedirectResponse(url="/student")
    return RedirectResponse(url="/login")


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    """Renders unified login page."""
    return templates.TemplateResponse(request=request, name="login.html")


@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, db: Session = Depends(get_db)):
    """Renders Admin Dashboard. Redirects to /login if unauthenticated or unauthorized."""
    user = _get_user_from_cookie(request, db)
    if not user or user.role != "admin":
        return RedirectResponse(url="/login?msg=admin_required")
    return templates.TemplateResponse(request=request, name="admin.html", context={"user": user})


@app.get("/student", response_class=HTMLResponse)
def student_page(request: Request, db: Session = Depends(get_db)):
    """Renders Student Dashboard. Redirects to /login if unauthenticated."""
    user = _get_user_from_cookie(request, db)
    if not user or user.role != "student":
        return RedirectResponse(url="/login?msg=student_required")
    return templates.TemplateResponse(request=request, name="student.html", context={"user": user})


@app.get("/canteen", response_class=HTMLResponse)
def canteen_page(request: Request, db: Session = Depends(get_db)):
    """Renders Canteen Staff QR Scanner Terminal."""
    user = _get_user_from_cookie(request, db)
    if not user or user.role not in ("staff", "admin"):
        return RedirectResponse(url="/login?msg=staff_required")
    return templates.TemplateResponse(request=request, name="scanner.html", context={"user": user})


@app.get("/download-project-zip", include_in_schema=False)
def download_project_zip():
    """Provides a 1-click download of the complete project folder bundle."""
    zip_path = "student-qr-lunch-system-complete.zip"
    if os.path.exists(zip_path):
        return FileResponse(
            path=zip_path,
            filename="student-qr-lunch-system-complete.zip",
            media_type="application/zip"
        )
    raise HTTPException(status_code=404, detail="Zip file not found.")
