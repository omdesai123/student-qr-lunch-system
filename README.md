# Student QR Lunch Coupon Management System

A digital lunch coupon management web application built for college dining halls (serving ~500 students). Every student receives a permanent, cryptographically secure QR code. Canteen staff scan the QR code via their device camera to verify eligibility and atomically redeem one lunch coupon per calendar day in the `Asia/Kolkata` timezone.

---

## Architecture Overview

```
+-----------------------------------------------------------------------------------+
|                                  BROWSER CLIENTS                                  |
|   +---------------------+   +---------------------+   +---------------------+     |
|   |   Admin Dashboard   |   |  Canteen QR Scanner |   |   Student Portal    |     |
|   |  (Desktop / Tablet) |   |  (Mobile / Camera)  |   |   (Digital Wallet)  |     |
|   +----------+----------+   +----------+----------+   +----------+----------+     |
+--------------|-------------------------|-------------------------|----------------+
               | (JWT / Cookie)          | (Camera Frame QR)       | (JWT / Cookie)
               v                         v                         v
+-----------------------------------------------------------------------------------+
|                              FASTAPI BACKEND SERVER                               |
|                                                                                   |
|  * Routers:                                                                       |
|    - /api/auth    : Unified Login, Role JWT issuance, HTTP-only Cookie Auth       |
|    - /api/admin   : Student CRUD, 500-Student CSV Import, QR ZIP Bundler, Stats   |
|    - /api/student : Digital Lunch Pass, QR PNG Generation, Today's Live Status    |
|    - /api/canteen : Atomic QR Verification, Duplicate Prevention, Manual Fallback |
|                                                                                   |
|  * Cryptographic Engine:                                                          |
|    - QR Token     : HMAC-SHA256(SecretKey, StudentID) -> 64-char Hex (No PII)     |
|    - DB Storage   : SHA-256(QR Token) -> Stored in database as qr_token_hash      |
|    - Timezone     : Asia/Kolkata (IST) calendar day tracking                      |
+----------------------------------------+------------------------------------------+
                                         | SQLAlchemy ORM
                                         v
+-----------------------------------------------------------------------------------+
|                                 SQLITE DATABASE                                   |
|                                                                                   |
|  * users       : id, username, password_hash, role, is_active, created_at         |
|  * students    : id, student_id, name, department, year, qr_token_hash, is_active |
|  * redemptions : id, student_id, redemption_date, redeemed_at, redeemed_by        |
|                  CONSTRAINT: UNIQUE(student_id, redemption_date)                  |
+-----------------------------------------------------------------------------------+
```

---

## Directory Structure

```
project/
├── app/
│   ├── __init__.py               # Application package definition
│   ├── config.py                 # Pydantic environment configuration (.env)
│   ├── database.py               # SQLAlchemy engine, session maker, get_db dependency
│   ├── models.py                 # Database models: User, Student, Redemption
│   ├── schemas.py                # Pydantic validation schemas
│   ├── security.py               # Bcrypt password hashing, JWT creation & decoding, RBAC
│   ├── qr_service.py             # QR derivation, SHA-256 hashing, PNG badge & ZIP bundler
│   ├── utils/
│   │   ├── __init__.py
│   │   └── timezone.py           # Asia/Kolkata date/time utilities
│   └── routers/
│       ├── __init__.py
│       ├── auth.py               # Login, logout, user profile endpoints
│       ├── admin.py              # Student management, CSV import/export, analytics, ZIP
│       ├── student.py            # Student dashboard, personal QR coupon & download
│       └── canteen.py            # Scanner verification, atomic redemption, manual fallback
├── static/
│   ├── css/
│   │   ├── styles.css            # Responsive blue & white college theme design system
│   │   └── scanner.css           # Viewfinder, laser animation, feedback overlays
│   └── js/
│       ├── vendor/
│       │   └── html5-qrcode.min.js # Bundled offline QR scanning library
│       ├── api.js                # Reusable fetch client, toast alerts, Web Audio synthesizer
│       ├── auth.js               # Unified sign-in form & 1-click test credentials
│       ├── admin.js              # Admin interactions, live filters, modals, pagination
│       ├── student.js            # Student digital pass live status & download
│       └── scanner.js            # Camera scanner controller, sound feedback, manual fallback
├── templates/
│   ├── base.html                 # Common shell with navbar and theme container
│   ├── login.html                # Unified portal sign-in with 1-click demo accounts
│   ├── admin.html                # Administrator dashboard and management console
│   ├── student.html              # Student mobile-ready digital coupon wallet
│   └── scanner.html              # Canteen staff camera scanner terminal
├── scripts/
│   ├── generate_sample_csv.py    # Generates 500 realistic college students in CSV format
│   └── seed_data.py              # Seeds default admin, staff, and initial students
├── tests/
│   ├── __init__.py
│   └── test_system.py            # 15 automated unit & concurrency tests
├── sample_500_students.csv       # Pre-generated 500-student test dataset
├── .env                          # Local environment variables
├── .env.example                  # Environment configuration template
├── requirements.txt              # Python package dependencies
└── main.py                       # FastAPI application entrypoint
```

---

## Security & Business Rules

1. **Zero Personal Data in QR Codes**:
   - QR codes contain only a 64-character cryptographic token derived using HMAC-SHA256 with a server secret (`QR_SECRET_SALT`).
   - The token contains no student ID, roll number, or personal identifiable information (PII).
2. **One-Way Token Hashing in Database**:
   - The database stores **only** the SHA-256 hash of the QR token (`qr_token_hash`).
   - Even if the database is compromised, QR tokens cannot be reversed or counterfeited.
3. **Database-Level Atomic Duplicate Prevention**:
   - `Redemption` table contains a compound unique constraint: `UNIQUE(student_id, redemption_date)`.
   - Simultaneous scans for the same student are safely serialized; duplicate scans trigger an `IntegrityError` that immediately returns `ALREADY_REDEEMED`.
4. **Asia/Kolkata Timezone Enforcement**:
   - Calendar date boundaries reset every day at 00:00 IST (`Asia/Kolkata`).
   - All audit logs record exact local IST timestamps.
5. **Inactive Student Blocking**:
   - Deactivated student accounts are rejected by the backend with an `INACTIVE_STUDENT` warning.
6. **Backend-Verified Decisions**:
   - The frontend never decides whether a meal is approved; all validations occur inside FastAPI transactions.

---

## Getting Started on Windows (PowerShell & VS Code)

### Prerequisites
- Python 3.10+ installed and added to `PATH`
- Visual Studio Code

### Step 1: Clone or Open Project in VS Code
Open the project directory in VS Code:
```powershell
code c:\Users\vkuser\Documents\project
```

Open a new PowerShell terminal in VS Code (`Ctrl + ~` or `Terminal -> New Terminal`).

### Step 2: Create and Activate Virtual Environment (Optional but Recommended)
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```
*(If PowerShell shows execution policy restrictions, run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process` first).*

### Step 3: Install Dependencies
```powershell
pip install -r requirements.txt
```

### Step 4: Seed Database and Generate Sample 500 Students
```powershell
python scripts/seed_data.py
```
This initializes `lunch_coupon.db` with:
- Administrator user: `admin` / `AdminPassword@2026`
- Canteen staff user: `canteen_staff` / `StaffPassword@2026`
- 50 pre-seeded sample students (`STU2026001` through `STU2026050`)
- `sample_500_students.csv` ready to test bulk import of 500 students!

### Step 5: Start the Web Application
```powershell
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Open your browser and navigate to:
- **Application Portal**: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **FastAPI Interactive Swagger Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## Default Credentials & Quick Test Access

The login page includes **1-Click Demo Buttons** that automatically fill in credentials:

| Role | Username / ID | Password | Access URL |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin` | `AdminPassword@2026` | `/admin` |
| **Canteen Staff** | `canteen_staff` | `StaffPassword@2026` | `/canteen` |
| **Sample Student 1** | `STU2026001` | `STU2026001` | `/student` |
| **Sample Student 2** | `STU2026002` | `STU2026002` | `/student` |
| **Sample Student 3** | `STU2026003` | `STU2026003` | `/student` |

---

## User Guide & Testing Workflows

### 1. Admin Dashboard (`/admin`)
- **Live Metrics**: Inspect Total Students, Active Eligible, Lunches Redeemed Today, and Remaining Unclaimed.
- **Search & Filter**: Search students by name or ID; filter by Department, Academic Year, or Active/Inactive status.
- **Add Student**: Add single students with custom or auto-generated passwords and immediate QR token derivation.
- **View & Download QR Badge**: Click the `QR` button next to any student to view and download their PNG coupon badge.
- **Download All QRs (ZIP)**: Click `Download All QRs (ZIP)` to bundle all student QR codes into an in-memory ZIP archive.
- **Import 500 Students**: Click `Import 500 Students (CSV)`, choose `sample_500_students.csv`, and run the import. Deduplication skips existing students automatically.
- **Redemption Audit History**: View today's redemptions or pick any past date; export report as CSV via `Export Report CSV`.

### 2. Student Portal (`/student`)
- Log in with `STU2026001` / `STU2026001`.
- View the **Campus Lunch Pass** digital card.
- Check today's status badge:
  - **Available Today** (pulsing green dot) when eligible.
  - **Redeemed Today** (checked) showing exact redemption time and verifying staff member.
- Click `Download QR (PNG)` to save the lunch badge to your device or mobile photo gallery.

### 3. Canteen Staff Scanner Terminal (`/canteen`)
- Log in with `canteen_staff` / `StaffPassword@2026`.
- **Camera Scanning**: Select your device's camera (back environment camera is selected by default on mobile phones).
- Point the camera at a student's QR coupon (either printed, on another phone screen, or from the `/student` tab).
- **Approved Scan**:
  - Plays a pleasant success chime.
  - Displays a large **Green Approval Screen** with the student's name, ID, department, and redemption timestamp.
  - Increments today's redemption counter and prepends the record to the recent feed.
- **Duplicate Scan Attempt**:
  - Scanning the same student on the same day triggers a prominent **Red Duplicate Warning Screen**.
  - Displays the exact time the coupon was already claimed earlier today and the verifying staff username.
- **Invalid / Inactive Student**:
  - Shows warning for deactivated students or unknown tokens.
- **Manual Fallback**:
  - If camera access is restricted or lighting is poor, enter the student ID (e.g. `STU2026002`) into the manual lookup box and click `Redeem Lunch`.

---

## Running the Automated Test Suite

A comprehensive test suite verifies authentication, cryptographic token derivation, atomic duplicate prevention, inactive student rejection, and concurrent race conditions:

```powershell
python tests/test_system.py
```

All 15 tests run in under 2 seconds and test:
1. `test_01_login_success`: Unified login & JWT issuance
2. `test_02_login_invalid_password`: 401 Unauthorized handling
3. `test_03_login_inactive_user`: 403 Forbidden handling
4. `test_04_qr_token_properties`: Cryptographic token properties & PNG generation
5. `test_05_canteen_qr_redemption_approved`: First-time approval
6. `test_06_canteen_duplicate_redemption_rejected`: Same-day duplicate rejection
7. `test_07_canteen_invalid_qr_rejected`: Invalid token rejection
8. `test_08_canteen_inactive_student_rejected`: Deactivated account handling
9. `test_09_manual_student_id_redemption`: Manual lookup fallback & duplicate check
10. `test_10_concurrent_simultaneous_redemptions`: 10 simultaneous threads fire concurrently against the same student; exactly 1 approved, 9 rejected via database unique constraint
11. `test_11_student_profile_status`: Real-time status reflection in student wallet
12. `test_12_admin_stats`: Dashboard metric computations
13. `test_13_admin_student_search_and_filter`: Directory search & filters
14. `test_14_admin_qr_zip_bundle`: ZIP streaming of all student QR codes
15. `test_15_admin_redemptions_export_csv`: CSV audit report export

---

## Production Deployment & HTTPS Guidance

1. **Environment Variables**:
   Update `.env` with a strong cryptographic secret:
   ```env
   SECRET_KEY="<generate-with-openssl-rand-hex-32>"
   QR_SECRET_SALT="<generate-with-openssl-rand-hex-32>"
   ```
2. **Reverse Proxy (Nginx) & SSL Certificate**:
   Camera access in web browsers (`navigator.mediaDevices.getUserMedia`) requires **HTTPS** (or `localhost`). For deployment on college servers:
   ```nginx
   server {
       listen 443 ssl http2;
       server_name dining.college.edu;

       ssl_certificate /etc/letsencrypt/live/dining.college.edu/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/dining.college.edu/privkey.pem;

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto https;
       }
   }
   ```
3. **Running with Production Process Manager (Systemd or PM2)**:
   ```bash
   gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000
   ```
#   s t u d e n t - q r - l u n c h - s y s t e m  
 