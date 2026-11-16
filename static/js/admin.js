// Admin Dashboard Interactions

let currentPage = 1;
const pageSize = 25;
let currentSearch = "";
let currentDept = "all";
let currentYear = "";
let currentStatus = "all";
let searchDebounceTimer = null;

document.addEventListener("DOMContentLoaded", () => {
  loadAdminStats();
  loadStudents(1);
  loadRedemptionHistory();

  // Search input handler with 350ms debounce
  const searchInput = document.getElementById("student-search");
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      clearTimeout(searchDebounceTimer);
      searchDebounceTimer = setTimeout(() => {
        currentSearch = e.target.value.trim();
        loadStudents(1);
      }, 350);
    });
  }

  // Filter change handlers
  const deptFilter = document.getElementById("dept-filter");
  if (deptFilter) {
    deptFilter.addEventListener("change", (e) => {
      currentDept = e.target.value;
      loadStudents(1);
    });
  }

  const yearFilter = document.getElementById("year-filter");
  if (yearFilter) {
    yearFilter.addEventListener("change", (e) => {
      currentYear = e.target.value;
      loadStudents(1);
    });
  }

  const statusFilter = document.getElementById("status-filter");
  if (statusFilter) {
    statusFilter.addEventListener("change", (e) => {
      currentStatus = e.target.value;
      loadStudents(1);
    });
  }

  // Add Student Form submission
  const addStudentForm = document.getElementById("add-student-form");
  if (addStudentForm) {
    addStudentForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      await handleAddStudent();
    });
  }

  // Edit Student Form submission
  const editStudentForm = document.getElementById("edit-student-form");
  if (editStudentForm) {
    editStudentForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      await handleEditStudent();
    });
  }

  // CSV Import Form submission
  const csvImportForm = document.getElementById("csv-import-form");
  if (csvImportForm) {
    csvImportForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      await handleCsvImport();
    });
  }
});

// Load live dashboard metrics
async function loadAdminStats() {
  try {
    const res = await API.request("/api/admin/stats");
    if (!res.ok) throw new Error("Failed to load dashboard metrics");
    const data = await res.json();

    document.getElementById("stat-total-students").textContent = data.total_students;
    document.getElementById("stat-active-students").textContent = data.active_students;
    document.getElementById("stat-redeemed-today").textContent = data.redeemed_today;
    document.getElementById("stat-remaining-today").textContent = data.remaining_eligible_today;
    if (document.getElementById("stat-redemption-pct")) {
      document.getElementById("stat-redemption-pct").textContent = `${data.redemption_percentage}% of active students`;
    }
    if (document.getElementById("current-date-display")) {
      document.getElementById("current-date-display").textContent = data.current_date;
    }
  } catch (err) {
    console.error(err);
  }
}

// Load student directory
async function loadStudents(page = 1) {
  currentPage = page;
  const tbody = document.getElementById("student-table-body");
  if (!tbody) return;

  tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:2rem;color:#64748b;">Loading students...</td></tr>`;

  try {
    let url = `/api/admin/students?page=${page}&limit=${pageSize}`;
    if (currentSearch) url += `&q=${encodeURIComponent(currentSearch)}`;
    if (currentDept && currentDept !== "all") url += `&department=${encodeURIComponent(currentDept)}`;
    if (currentYear) url += `&year=${encodeURIComponent(currentYear)}`;
    if (currentStatus && currentStatus !== "all") url += `&status=${encodeURIComponent(currentStatus)}`;

    const res = await API.request(url);
    if (!res.ok) throw new Error("Failed to load students");
    const data = await res.json();

    if (data.items.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:2.5rem;color:#94a3b8;">No matching student records found.</td></tr>`;
      renderPagination(0, 0, 0);
      return;
    }

    tbody.innerHTML = data.items.map(s => `
      <tr>
        <td><strong>${s.student_id}</strong></td>
        <td>${s.name}</td>
        <td>${s.department}</td>
        <td>Year ${s.year}</td>
        <td>
          <span class="badge ${s.is_active ? 'badge-active' : 'badge-inactive'}">
            ${s.is_active ? 'Active' : 'Inactive'}
          </span>
        </td>
        <td>
          <span class="badge ${s.today_status === 'REDEEMED' ? 'badge-redeemed' : 'badge-available'}">
            ${s.today_status === 'REDEEMED' ? `Redeemed (${s.redeemed_at_str || ''})` : 'Available'}
          </span>
        </td>
        <td style="white-space:nowrap;text-align:right;">
          <button class="btn btn-sm btn-secondary" onclick="viewStudentQr('${s.student_id}', '${escapeHtml(s.name)}')" title="View/Download QR">
            QR
          </button>
          <button class="btn btn-sm btn-secondary" onclick="openEditStudentModal(${s.id})" title="Edit Details">
            Edit
          </button>
          <button class="btn btn-sm ${s.is_active ? 'btn-secondary' : 'btn-success'}" onclick="toggleStudentStatus(${s.id})" title="Toggle Active">
            ${s.is_active ? 'Deactivate' : 'Activate'}
          </button>
          <button class="btn btn-sm btn-danger" onclick="deleteStudent(${s.id}, '${s.student_id}')" title="Delete Student">
            Del
          </button>
        </td>
      </tr>
    `).join("");

    renderPagination(data.total, data.page, data.total_pages);
  } catch (err) {
    console.error(err);
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:2rem;color:#ef4444;">Failed to load students: ${err.message}</td></tr>`;
  }
}

function renderPagination(total, page, totalPages) {
  const container = document.getElementById("student-pagination");
  if (!container) return;

  if (total === 0) {
    container.innerHTML = `<span>0 students</span>`;
    return;
  }

  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);

  container.innerHTML = `
    <span>Showing <strong>${start} - ${end}</strong> of <strong>${total}</strong> students</span>
    <div style="display:flex;gap:0.5rem;">
      <button class="btn btn-sm btn-secondary" ${page <= 1 ? 'disabled' : ''} onclick="loadStudents(${page - 1})">&larr; Prev</button>
      <span style="display:inline-flex;align-items:center;padding:0 0.5rem;font-weight:600;">Page ${page} of ${totalPages}</span>
      <button class="btn btn-sm btn-secondary" ${page >= totalPages ? 'disabled' : ''} onclick="loadStudents(${page + 1})">Next &rarr;</button>
    </div>
  `;
}

// Add Student Handler
async function handleAddStudent() {
  const stuId = document.getElementById("add-student-id").value.trim().toUpperCase();
  const name = document.getElementById("add-name").value.trim();
  const department = document.getElementById("add-department").value;
  const year = parseInt(document.getElementById("add-year").value, 10);
  const password = document.getElementById("add-password").value.trim();
  const isActive = document.getElementById("add-active").checked;

  try {
    const res = await API.request("/api/admin/students", {
      method: "POST",
      body: {
        student_id: stuId,
        name: name,
        department: department,
        year: year,
        password: password || undefined,
        is_active: isActive
      }
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to add student");

    showToast(`Student ${stuId} added successfully!`, "success");
    closeModal("modal-add-student");
    document.getElementById("add-student-form").reset();
    loadStudents(1);
    loadAdminStats();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

// Edit Student Modal
async function openEditStudentModal(id) {
  try {
    const res = await API.request(`/api/admin/students/${id}`);
    if (!res.ok) throw new Error("Failed to load student details");
    const data = await res.json();

    document.getElementById("edit-id").value = data.id;
    document.getElementById("edit-student-id-display").value = data.student_id;
    document.getElementById("edit-name").value = data.name;
    document.getElementById("edit-department").value = data.department;
    document.getElementById("edit-year").value = data.year;
    document.getElementById("edit-active").checked = data.is_active;
    document.getElementById("edit-password").value = "";

    openModal("modal-edit-student");
  } catch (err) {
    showToast(err.message, "danger");
  }
}

async function handleEditStudent() {
  const id = document.getElementById("edit-id").value;
  const name = document.getElementById("edit-name").value.trim();
  const department = document.getElementById("edit-department").value;
  const year = parseInt(document.getElementById("edit-year").value, 10);
  const isActive = document.getElementById("edit-active").checked;
  const password = document.getElementById("edit-password").value.trim();

  try {
    const payload = {
      name,
      department,
      year,
      is_active: isActive
    };
    if (password) payload.password = password;

    const res = await API.request(`/api/admin/students/${id}`, {
      method: "PUT",
      body: payload
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to update student");
    }

    showToast("Student updated successfully!", "success");
    closeModal("modal-edit-student");
    loadStudents(currentPage);
    loadAdminStats();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

// Toggle Student Status
async function toggleStudentStatus(id) {
  try {
    const res = await API.request(`/api/admin/students/${id}/toggle-status`, { method: "POST" });
    if (!res.ok) throw new Error("Failed to change student status");
    const data = await res.json();
    showToast(`Student ${data.student_id} is now ${data.is_active ? 'Active' : 'Inactive'}`, "info");
    loadStudents(currentPage);
    loadAdminStats();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

// Delete Student
async function deleteStudent(id, studentId) {
  if (!confirm(`Are you sure you want to permanently delete student ${studentId}? All past redemption logs for this student will also be removed.`)) {
    return;
  }

  try {
    const res = await API.request(`/api/admin/students/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Failed to delete student");
    showToast(`Student ${studentId} deleted.`, "info");
    loadStudents(currentPage);
    loadAdminStats();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

// View & Download QR Modal
function viewStudentQr(studentId, studentName) {
  const modalImg = document.getElementById("qr-preview-img");
  const modalTitle = document.getElementById("qr-modal-title");
  const downloadLink = document.getElementById("qr-modal-download-btn");

  const qrUrl = `/api/admin/qr/${studentId}?t=${Date.now()}`;
  modalImg.src = qrUrl;
  modalTitle.textContent = `Lunch Coupon: ${studentName} (${studentId})`;
  downloadLink.href = qrUrl;
  downloadLink.setAttribute("download", `QR_${studentId}.png`);

  openModal("modal-view-qr");
}

// Download All QR Codes as ZIP
async function downloadAllQrZip() {
  const btn = document.getElementById("btn-download-zip");
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span> Packaging ZIP...`;
  }

  try {
    showToast("Generating ZIP bundle of all student QR codes. Please wait...", "info");
    window.location.href = "/api/admin/qr-zip";
  } catch (err) {
    showToast("Error initiating ZIP download: " + err.message, "danger");
  } finally {
    setTimeout(() => {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg> Download All QRs (ZIP)`;
      }
    }, 3000);
  }
}

// CSV Bulk Import Handler
async function handleCsvImport() {
  const fileInput = document.getElementById("csv-file-input");
  const submitBtn = document.getElementById("csv-import-submit-btn");
  const resultBox = document.getElementById("csv-import-result");

  if (!fileInput.files || fileInput.files.length === 0) {
    showToast("Please select a CSV file to upload.", "warning");
    return;
  }

  const file = fileInput.files[0];
  const formData = new FormData();
  formData.append("file", file);

  submitBtn.disabled = true;
  submitBtn.textContent = "Importing & Generating QRs...";
  resultBox.style.display = "none";

  try {
    const res = await API.request("/api/admin/import-csv", {
      method: "POST",
      body: formData
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "CSV Import failed.");

    resultBox.style.display = "block";
    resultBox.innerHTML = `
      <div style="background:#ecfdf5;border:1px solid #10b981;border-radius:8px;padding:1rem;color:#065f46;">
        <h4 style="font-weight:700;margin-bottom:0.4rem;">Import Complete!</h4>
        <p>Total rows processed: <strong>${data.total_rows}</strong></p>
        <p>Successfully imported: <strong style="color:#059669;">${data.imported}</strong></p>
        <p>Duplicates skipped: <strong>${data.skipped_duplicates}</strong></p>
        ${data.errors.length ? `<div style="margin-top:0.5rem;font-size:0.8rem;color:#b91c1c;"><strong>Issues encountered:</strong><ul>${data.errors.map(e => `<li>${e}</li>`).join('')}</ul></div>` : ''}
      </div>
    `;

    showToast(`Successfully imported ${data.imported} students!`, "success");
    loadStudents(1);
    loadAdminStats();
  } catch (err) {
    resultBox.style.display = "block";
    resultBox.innerHTML = `<div style="background:#fef2f2;border:1px solid #ef4444;border-radius:8px;padding:1rem;color:#991b1b;"><strong>Import Error:</strong> ${err.message}</div>`;
    showToast(err.message, "danger");
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Start Import";
  }
}

// Redemption History
async function loadRedemptionHistory(dateStr = "") {
  const tbody = document.getElementById("redemption-table-body");
  if (!tbody) return;

  tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:1.5rem;color:#64748b;">Loading redemption logs...</td></tr>`;

  try {
    let url = `/api/admin/redemptions?limit=100`;
    if (dateStr) url += `&redemption_date=${encodeURIComponent(dateStr)}`;

    const res = await API.request(url);
    if (!res.ok) throw new Error("Failed to load redemptions");
    const data = await res.json();

    if (data.items.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:2rem;color:#94a3b8;">No lunch redemptions recorded for this date.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.items.map(r => `
      <tr>
        <td><strong>${r.student_id}</strong></td>
        <td>${r.student_name}</td>
        <td>${r.department}</td>
        <td>Year ${r.year}</td>
        <td>${r.redeemed_at}</td>
        <td><span class="role-pill staff">${r.redeemed_by}</span></td>
      </tr>
    `).join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:1.5rem;color:#ef4444;">${err.message}</td></tr>`;
  }
}

function handleDateFilterChange(e) {
  loadRedemptionHistory(e.target.value);
}

function exportRedemptionsCsv() {
  const dateInput = document.getElementById("history-date-picker");
  const dateVal = dateInput ? dateInput.value : "";
  window.location.href = `/api/admin/export-redemptions-csv?redemption_date=${encodeURIComponent(dateVal)}`;
}

// Modal UI Helpers
function openModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.classList.add("show");
}

function closeModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.classList.remove("show");
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}
