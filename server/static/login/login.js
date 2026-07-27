document.addEventListener("DOMContentLoaded", function () {
  const form = document.getElementById("login-form");
  const usernameInput = document.getElementById("username");
  const passwordInput = document.getElementById("password");
  const loginBtn = document.getElementById("login-btn");
  const togglePwd = document.getElementById("toggle-pwd");
  const eyeIcon = document.getElementById("eye-icon");

  // ── Focus automatique sur le champ utilisateur ──────────────────
  if (usernameInput) usernameInput.focus();

  // ── Toggle affichage mot de passe ───────────────────────────────
  if (togglePwd && passwordInput) {
    togglePwd.addEventListener("click", function () {
      const isHidden = passwordInput.type === "password";
      passwordInput.type = isHidden ? "text" : "password";

      // Changer l'icône œil ouvert / barré
      eyeIcon.innerHTML = isHidden
        ? /* œil barré */
          `<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
           <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
           <line x1="1" y1="1" x2="23" y2="23"/>`
        : /* œil ouvert */
          `<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
           <circle cx="12" cy="12" r="3"/>`;
    });
  }

  // ── Effacer erreur inline au focus ──────────────────────────────
  [usernameInput, passwordInput].forEach((input) => {
    if (!input) return;
    input.addEventListener("input", () => {
      input.classList.remove("input-error");
      const fieldId =
        input.id === "username" ? "error-username" : "error-password";
      clearFieldError(fieldId);
    });
  });

  // ── Validation à la soumission ──────────────────────────────────
  if (form) {
    form.addEventListener("submit", function (e) {
      let valid = true;

      // Réinitialiser les erreurs
      clearAllErrors();

      if (!usernameInput.value.trim()) {
        e.preventDefault();
        showFieldError(
          "error-username",
          usernameInput,
          "Nom d'utilisateur requis",
        );
        valid = false;
      }

      if (!passwordInput.value) {
        e.preventDefault();
        showFieldError("error-password", passwordInput, "Mot de passe requis");
        valid = false;
      }

      if (valid) {
        // Afficher l'état loading sur le bouton
        loginBtn.classList.add("loading");
        loginBtn.disabled = true;
      }
    });
  }
});

// ── Affiche une erreur sous un champ ────────────────────────────────
function showFieldError(errorId, inputEl, message) {
  const el = document.getElementById(errorId);
  if (el) {
    el.textContent = message;
    el.style.display = "block";
  }
  if (inputEl) inputEl.classList.add("input-error");
  if (inputEl) inputEl.focus();
}

// ── Efface l'erreur d'un champ ──────────────────────────────────────
function clearFieldError(errorId) {
  const el = document.getElementById(errorId);
  if (el) {
    el.textContent = "";
    el.style.display = "none";
  }
}

// ── Efface toutes les erreurs ────────────────────────────────────────
function clearAllErrors() {
  clearFieldError("error-username");
  clearFieldError("error-password");
  document.getElementById("username")?.classList.remove("input-error");
  document.getElementById("password")?.classList.remove("input-error");
}
