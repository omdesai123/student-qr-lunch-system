// Canteen Staff QR Scanner and Redemption Terminal

let html5QrCode = null;
let isScanning = false;
let isProcessingScan = false;
let currentCameraId = null;
let lastScannedToken = "";
let lastScanTime = 0;

document.addEventListener("DOMContentLoaded", () => {
  initScanner();
  loadCanteenStats();
  loadRecentRedemptions();

  // Manual fallback form submission
  const manualForm = document.getElementById("manual-redeem-form");
  if (manualForm) {
    manualForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      await handleManualRedemption();
    });
  }

  // Camera switch selector
  const cameraSelect = document.getElementById("camera-select");
  if (cameraSelect) {
    cameraSelect.addEventListener("change", (e) => {
      if (e.target.value) {
        currentCameraId = e.target.value;
        if (isScanning) {
          stopScanner().then(() => startScanner(currentCameraId));
        }
      }
    });
  }
});

// Initialize Html5Qrcode and populate available cameras
async function initScanner() {
  const cameraSelect = document.getElementById("camera-select");

  try {
    if (typeof Html5Qrcode === "undefined") {
      console.warn("Html5Qrcode library not yet loaded.");
      return;
    }

    html5QrCode = new Html5Qrcode("qr-reader");

    const cameras = await Html5Qrcode.getCameras();
    if (cameras && cameras.length > 0) {
      if (cameraSelect) {
        cameraSelect.innerHTML = cameras.map((cam, idx) => `
          <option value="${cam.id}" ${idx === 0 || cam.label.toLowerCase().includes("back") ? "selected" : ""}>
            ${cam.label || `Camera ${idx + 1}`}
          </option>
        `).join("");
      }

      // Prefer back camera by default for mobile phone scanning
      const backCam = cameras.find(c => c.label.toLowerCase().includes("back") || c.label.toLowerCase().includes("environment"));
      currentCameraId = backCam ? backCam.id : cameras[0].id;

      // Automatically start scanner
      startScanner(currentCameraId);
    } else {
      if (cameraSelect) {
        cameraSelect.innerHTML = `<option value="">No cameras detected</option>`;
      }
      showToast("No camera detected on this device. You can use manual Student ID entry.", "warning");
    }
  } catch (err) {
    console.error("Camera init error:", err);
    if (cameraSelect) {
      cameraSelect.innerHTML = `<option value="">Camera access denied/unavailable</option>`;
    }
  }
}

async function startScanner(cameraId) {
  if (!html5QrCode || isScanning) return;

  const startBtn = document.getElementById("btn-toggle-camera");
  const laser = document.getElementById("scan-laser");

  try {
    const config = {
      fps: 15,
      qrbox: { width: 250, height: 250 },
      aspectRatio: 1.0,
      experimentalFeatures: {
        useBarCodeDetectorIfSupported: true
      }
    };

    await html5QrCode.start(
      cameraId ? { deviceId: { exact: cameraId } } : { facingMode: "environment" },
      config,
      onScanSuccess,
      onScanFailure
    );

    isScanning = true;
    if (startBtn) {
      startBtn.textContent = "Pause Camera";
      startBtn.classList.remove("btn-primary");
      startBtn.classList.add("btn-secondary");
    }
    if (laser) laser.style.display = "block";
  } catch (err) {
    console.error("Failed to start camera:", err);
    showToast("Camera permission was denied or camera is in use by another app.", "danger");
  }
}

async function stopScanner() {
  if (!html5QrCode || !isScanning) return;

  const startBtn = document.getElementById("btn-toggle-camera");
  const laser = document.getElementById("scan-laser");

  try {
    await html5QrCode.stop();
    isScanning = false;
    if (startBtn) {
      startBtn.textContent = "Resume Camera";
      startBtn.classList.remove("btn-secondary");
      startBtn.classList.add("btn-primary");
    }
    if (laser) laser.style.display = "none";
  } catch (err) {
    console.error("Failed to stop camera:", err);
  }
}

function toggleScanner() {
  if (isScanning) {
    stopScanner();
  } else {
    startScanner(currentCameraId);
  }
}

// Callback when QR code is decoded from camera frame
async function onScanSuccess(decodedText) {
  const now = Date.now();
  // 2.5 second cooldown between processing same scan
  if (isProcessingScan || (decodedText === lastScannedToken && now - lastScanTime < 3000)) {
    return;
  }

  lastScannedToken = decodedText;
  lastScanTime = now;
  isProcessingScan = true;

  try {
    await processQrToken(decodedText);
  } finally {
    // Release processing lock after brief moment
    setTimeout(() => {
      isProcessingScan = false;
    }, 1500);
  }
}

function onScanFailure(error) {
  // Silent frame miss - normal while camera is searching for QR
}

// Send token to backend
async function processQrToken(token) {
  try {
    const res = await API.request("/api/canteen/redeem/scan", {
      method: "POST",
      body: { qr_token: token }
    });

    const result = await res.json();
    renderVerificationResult(result);
  } catch (err) {
    console.error("Scan verification network error:", err);
    renderVerificationResult({
      success: false,
      status: "NETWORK_ERROR",
      message: "Server connection failed: " + err.message
    });
  }
}

// Manual Student ID Fallback
async function handleManualRedemption() {
  const input = document.getElementById("manual-student-id");
  const btn = document.getElementById("manual-redeem-btn");
  const stuId = input.value.trim().toUpperCase();

  if (!stuId) {
    showToast("Please enter a Student ID.", "warning");
    return;
  }

  btn.disabled = true;
  btn.textContent = "Verifying...";

  try {
    const res = await API.request("/api/canteen/redeem/manual", {
      method: "POST",
      body: { student_id: stuId }
    });

    const result = await res.json();
    renderVerificationResult(result);
    input.value = "";
  } catch (err) {
    renderVerificationResult({
      success: false,
      status: "NETWORK_ERROR",
      message: "Network error: " + err.message
    });
  } finally {
    btn.disabled = false;
    btn.textContent = "Redeem Lunch";
  }
}

// Render prominent visual feedback card
function renderVerificationResult(res) {
  const banner = document.getElementById("verification-result-banner");
  if (!banner) return;

  banner.className = "result-banner show";

  if (res.status === "APPROVED") {
    SoundFx.playSuccess();
    banner.classList.add("approved");
    banner.innerHTML = `
      <div class="result-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>
      </div>
      <div class="result-title">LUNCH APPROVED</div>
      <div class="result-desc">${res.message}</div>
      <div class="result-student-badge">
        <div><strong>Student:</strong> ${res.student.name}</div>
        <div><strong>ID:</strong> ${res.student.student_id}</div>
        <div><strong>Department:</strong> ${res.student.department} (Year ${res.student.year})</div>
        <div><strong>Redeemed At:</strong> ${res.redemption_time}</div>
      </div>
      <div style="margin-top:1rem;">
        <button class="btn btn-sm btn-primary" onclick="dismissResultBanner()">Scan Next Student</button>
      </div>
    `;

    // Update live counters and recent logs
    loadCanteenStats();
    loadRecentRedemptions();

  } else if (res.status === "ALREADY_REDEEMED") {
    SoundFx.playWarning();
    banner.classList.add("already_redeemed");
    banner.innerHTML = `
      <div class="result-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
      </div>
      <div class="result-title">ALREADY REDEEMED TODAY</div>
      <div class="result-desc">Coupon already used earlier today!</div>
      <div class="result-student-badge">
        ${res.student ? `
          <div><strong>Student:</strong> ${res.student.name} (${res.student.student_id})</div>
          <div><strong>Department:</strong> ${res.student.department}</div>
        ` : ''}
        <div><strong>Originally Claimed:</strong> ${res.redemption_time || 'Earlier today'}</div>
        <div><strong>Verified By:</strong> ${res.redeemed_by || 'Staff'}</div>
      </div>
      <div style="margin-top:1rem;">
        <button class="btn btn-sm btn-danger" onclick="dismissResultBanner()">Dismiss Warning</button>
      </div>
    `;

  } else {
    // Invalid token, inactive student, or not found
    SoundFx.playError();
    banner.classList.add("invalid");
    banner.innerHTML = `
      <div class="result-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
      </div>
      <div class="result-title">${res.status === "INACTIVE_STUDENT" ? "STUDENT INACTIVE" : "INVALID COUPON"}</div>
      <div class="result-desc">${res.message}</div>
      <div style="margin-top:1rem;">
        <button class="btn btn-sm btn-secondary" onclick="dismissResultBanner()">Try Again</button>
      </div>
    `;
  }
}

function dismissResultBanner() {
  const banner = document.getElementById("verification-result-banner");
  if (banner) {
    banner.className = "result-banner";
    banner.innerHTML = "";
  }
}

// Load Canteen Metrics
async function loadCanteenStats() {
  try {
    const res = await API.request("/api/canteen/stats");
    if (!res.ok) return;
    const data = await res.json();
    const countEl = document.getElementById("canteen-today-count");
    if (countEl) countEl.textContent = data.today_redemptions;
  } catch (err) {
    console.error(err);
  }
}

// Load Recent Redemptions List
async function loadRecentRedemptions() {
  const container = document.getElementById("canteen-recent-list");
  if (!container) return;

  try {
    const res = await API.request("/api/canteen/recent");
    if (!res.ok) return;
    const data = await res.json();

    if (!data.recent || data.recent.length === 0) {
      container.innerHTML = `<div style="text-align:center;padding:1.5rem;color:#94a3b8;font-size:0.85rem;">No redemptions yet today.</div>`;
      return;
    }

    container.innerHTML = data.recent.map(r => `
      <div class="recent-item">
        <div>
          <div class="stu-name">${r.student_name} <span style="font-weight:normal;color:#64748b;">(${r.student_id})</span></div>
          <div class="stu-dept">${r.department} • Year ${r.year}</div>
        </div>
        <div class="time-pill">${r.redeemed_at}</div>
      </div>
    `).join("");
  } catch (err) {
    console.error(err);
  }
}

function toggleAudioMute() {
  SoundFx.muted = !SoundFx.muted;
  const btn = document.getElementById("btn-audio-toggle");
  if (btn) {
    btn.innerHTML = SoundFx.muted
      ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="1" y1="1" x2="23" y2="23"/><path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6"/></svg> Unmute Audio`
      : `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/></svg> Audio On`;
  }
}
