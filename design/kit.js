(() => {
  const KEY = "alpi-design-theme";
  function setTheme(theme) {
    document.documentElement.dataset.mode = theme;
    try {
      localStorage.setItem(KEY, theme);
    } catch {}
    document.querySelectorAll("[data-kit-theme]").forEach((button) => {
      const active = button.dataset.kitTheme === theme;
      button.setAttribute("aria-pressed", String(active));
    });
  }
  let saved = null;
  try {
    saved = localStorage.getItem(KEY);
  } catch {}
  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-kit-theme]");
    if (button) setTheme(button.dataset.kitTheme);
  });
  setTheme(saved || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
})();
