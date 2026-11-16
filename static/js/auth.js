// Authentication UI Logic

document.addEventListener("DOMContentLoaded", () => {
  const loginForm = document.getElementById("login-form");
  const errorMsg = document.getElementById("login-error");
  const submitBtn = document.getElementById("login-btn");

  if (loginForm) {
    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const username = document.getElementById("username").value.trim();
      const password = document.getElementById("password").value;

      if (!username || !password) {
        showError("Please enter both username and password.");
        return;
      }

      submitBtn.disabled = true;
      submitBtn.textContent = "Authenticating...";
      if (errorMsg) errorMsg.style.display = "none";

      try {
        const res = await fetch("/api/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, password })
        });

        const data = await res.json();

        if (!res.ok) {
          throw new Error(data.detail || "Authentication failed. Check credentials.");
        }

        // Save token and user info
        API.setToken(data.access_token);
        API.setCurrentUser(data.user);

        // Redirect according to user role
        redirectToRoleDashboard(data.user.role);
      } catch (err) {
        showError(err.message);
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "Sign In to Portal";
      }
    });
  }

  function showError(msg) {
    if (errorMsg) {
      errorMsg.textContent = msg;
      errorMsg.style.display = "block";
    } else {
      showToast(msg, "danger");
    }
  }
});

function redirectToRoleDashboard(role) {
  if (role === "admin") {
    window.location.href = "/admin";
  } else if (role === "staff") {
    window.location.href = "/canteen";
  } else if (role === "student") {
    window.location.href = "/student";
  } else {
    window.location.href = "/login";
  }
}

// Quick demo login fill
function fillDemoAccount(role) {
  const userField = document.getElementById("username");
  const passField = document.getElementById("password");
  if (!userField || !passField) return;

  if (role === "admin") {
    userField.value = "admin";
    passField.value = "AdminPassword@2026";
  } else if (role === "staff") {
    userField.value = "canteen_staff";
    passField.value = "StaffPassword@2026";
  } else if (role === "student") {
    userField.value = "STU2026001";
    passField.value = "STU2026001";
  }
}
