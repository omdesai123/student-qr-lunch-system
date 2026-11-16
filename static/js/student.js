// Student Portal Interactive Logic

document.addEventListener("DOMContentLoaded", () => {
  loadStudentDashboard();
});

async function loadStudentDashboard() {
  const profileLoader = document.getElementById("profile-loader");
  const profileContent = document.getElementById("profile-content");

  try {
    const res = await API.request("/api/student/profile");
    if (!res.ok) throw new Error("Failed to load student profile");
    const data = await res.json();

    if (profileLoader) profileLoader.style.display = "none";
    if (profileContent) profileContent.style.display = "block";

    // Fill profile fields
    document.getElementById("student-name-display").textContent = data.name;
    document.getElementById("student-id-display").textContent = data.student_id;
    document.getElementById("student-dept-display").textContent = data.department;
    document.getElementById("student-year-display").textContent = `Year ${data.year}`;
    document.getElementById("today-date-display").textContent = data.today_date;

    // Status indicator
    const statusBox = document.getElementById("coupon-status-box");
    const statusText = document.getElementById("coupon-status-text");
    const statusTime = document.getElementById("coupon-redeemed-time");

    if (data.today_status === "REDEEMED") {
      statusBox.className = "coupon-status-box redeemed";
      statusText.innerHTML = `
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
        <span>Redeemed Today</span>
      `;
      statusTime.textContent = `Claimed at ${data.redeemed_at} (Verified by ${data.redeemed_by})`;
      statusTime.style.display = "block";
    } else {
      statusBox.className = "coupon-status-box available";
      statusText.innerHTML = `
        <div class="status-pulse-dot"></div>
        <span>Lunch Coupon Available</span>
      `;
      statusTime.textContent = "Present this QR code to the canteen staff counter for today's lunch.";
      statusTime.style.display = "block";
    }

    // Set QR image source
    const qrImg = document.getElementById("student-qr-image");
    if (qrImg) {
      qrImg.src = `/api/student/qr-image?t=${Date.now()}`;
    }

    // Download button link
    const downloadBtn = document.getElementById("btn-download-qr");
    if (downloadBtn) {
      downloadBtn.href = "/api/student/download-qr";
      downloadBtn.setAttribute("download", `QR_Lunch_Coupon_${data.student_id}.png`);
    }

  } catch (err) {
    console.error(err);
    showToast(err.message, "danger");
  }
}
