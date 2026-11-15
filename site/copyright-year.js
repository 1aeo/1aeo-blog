/* Shared footer year for 1AEO pages. No network requests or stored data. */
(() => {
  "use strict";

  const updateCopyrightYear = () => {
    const year = String(new Date().getFullYear());
    document.querySelectorAll("[data-copyright-year]").forEach((element) => {
      element.textContent = year;
    });
  };

  updateCopyrightYear();
  window.addEventListener("pageshow", updateCopyrightYear);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") updateCopyrightYear();
  });
})();
