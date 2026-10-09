/**
 * PlantDex Main JavaScript
 * Handles dark/light theme switching, toast auto-dismiss, and PWA registration.
 */

// Theme Management
(function initTheme() {
  const savedTheme = localStorage.getItem("plantdex-theme");
  const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  const activeTheme = savedTheme || (prefersDark ? "dark" : "light");
  document.documentElement.setAttribute("data-theme", activeTheme);
})();

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || "light";
  const next = current === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("plantdex-theme", next);
  updateThemeIcon(next);
}

function updateThemeIcon(theme) {
  const icon = document.getElementById("theme-toggle-icon");
  if (icon) {
    icon.textContent = theme === "dark" ? "☀️" : "🌙";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const theme = document.documentElement.getAttribute("data-theme") || "light";
  updateThemeIcon(theme);

  // Auto-dismiss flash toasts after 5 seconds
  const toasts = document.querySelectorAll(".flash-toast");
  toasts.forEach((toast) => {
    setTimeout(() => {
      toast.style.transition = "opacity 0.4s ease, transform 0.4s ease";
      toast.style.opacity = "0";
      toast.style.transform = "translateY(-10px)";
      setTimeout(() => toast.remove(), 400);
    }, 5000);
  });

  // Register PWA Service Worker if supported
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch((err) => {
      console.debug("PWA ServiceWorker registration notice:", err);
    });
  }
});

function closeCatchModal() {
  const modal = document.getElementById("catch-modal");
  if (modal) {
    modal.style.transition = "opacity 0.3s ease";
    modal.style.opacity = "0";
    setTimeout(() => modal.remove(), 300);
  }
}
