import hmac
import hashlib
import io
import zipfile
from typing import List, Tuple
import qrcode
from PIL import Image, ImageDraw, ImageFont
from app.config import settings


def derive_qr_token(student_id: str) -> str:
    """
    Derives a permanent, unpredictable, cryptographically secure QR token for a student.
    Does not contain the student ID or any personal info.
    Format: 64-character hex string.
    """
    key = settings.QR_SECRET_SALT.encode("utf-8")
    message = f"COLLEGE_LUNCH_COUPON_V1:{student_id.strip().upper()}".encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def hash_qr_token(token: str) -> str:
    """
    Computes the SHA-256 hash of a scanned QR token string.
    This SHA-256 hash is what is stored in and queried against the database.
    """
    return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()


def generate_qr_image_bytes(token: str, student_id: str = "", student_name: str = "") -> bytes:
    """
    Generates a high-quality, high-contrast QR code image (PNG bytes).
    Optionally embeds a professional college card header/footer if student info is provided.
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=3,
    )
    qr.add_data(token)
    qr.make(fit=True)

    # Base QR image in crisp black & white
    qr_img = qr.make_image(fill_color="#0f172a", back_color="#ffffff").convert("RGBA")

    # If student info is provided, let's create a beautiful student lunch badge
    if student_id and student_name:
        badge_w = 400
        qr_w, qr_h = qr_img.size
        # Resize QR image to fit neatly
        target_qr_size = 320
        qr_resized = qr_img.resize((target_qr_size, target_qr_size), Image.Resampling.LANCZOS)

        badge_h = target_qr_size + 140
        card = Image.new("RGBA", (badge_w, badge_h), color="#ffffff")
        draw = ImageDraw.Draw(card)

        # Header background banner (College Blue #1e40af)
        draw.rectangle([(0, 0), (badge_w, 65)], fill="#1e40af")

        # Subtle card border
        draw.rectangle([(0, 0), (badge_w - 1, badge_h - 1)], outline="#cbd5e1", width=2)

        # Draw header text
        header_text = "CAMPUS LUNCH COUPON"
        draw.text((badge_w // 2, 22), header_text, fill="#ffffff", anchor="mm")
        draw.text((badge_w // 2, 45), "COLLEGE DINING SERVICES", fill="#93c5fd", anchor="mm")

        # Paste QR code centered
        paste_x = (badge_w - target_qr_size) // 2
        paste_y = 75
        card.paste(qr_resized, (paste_x, paste_y), qr_resized)

        # Footer text: Student ID and Name
        draw.text((badge_w // 2, paste_y + target_qr_size + 18), f"{student_name} ({student_id})", fill="#0f172a", anchor="mm")
        draw.text((badge_w // 2, paste_y + target_qr_size + 42), "Present to Canteen Staff • Valid Daily", fill="#64748b", anchor="mm")

        buf = io.BytesIO()
        card.save(buf, format="PNG", quality=95)
        return buf.getvalue()
    else:
        # Standalone QR code
        buf = io.BytesIO()
        qr_img.save(buf, format="PNG")
        return buf.getvalue()


def generate_all_qr_zip(students: List[Tuple[str, str, str]]) -> bytes:
    """
    Generates an in-memory ZIP archive containing individual QR code PNGs for a list of students.
    students: list of (student_id, name, department)
    """
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for stu_id, name, dept in students:
            token = derive_qr_token(stu_id)
            img_bytes = generate_qr_image_bytes(token, student_id=stu_id, student_name=name)
            # Safe filename: STU1001_John_Doe.png
            clean_name = "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
            filename = f"QR_{stu_id}_{clean_name}.png"
            zf.writestr(filename, img_bytes)

    zip_buffer.seek(0)
    return zip_buffer.getvalue()
