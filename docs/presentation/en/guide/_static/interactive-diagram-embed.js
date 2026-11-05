// Share the page's actual Sphinx palette and theme with this isolated graphic.
(() => {
  const frames = () => document.querySelectorAll("iframe.interactive-learning-diagram");
  const tokenNames = [
    "--pst-color-background", "--pst-color-text-base", "--pst-color-text-muted",
    "--pst-color-surface", "--pst-color-primary", "--pst-font-family-base",
    "--nv-color-green",
  ];
  const syncTheme = (frame) => {
    const styles = getComputedStyle(document.documentElement);
    const tokens = Object.fromEntries(tokenNames.map(name => [name, styles.getPropertyValue(name).trim()])
      .filter(([, value]) => value));
    const theme = document.documentElement.dataset.theme ||
      (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    frame.contentWindow?.postMessage({ type: "interactive-learning-diagram:theme", theme, tokens }, window.location.origin);
  };

  // Accept resize/readiness messages only from the known diagram frames.
  window.addEventListener("message", (event) => {
    if (event.origin !== window.location.origin) return;
    frames().forEach((frame) => {
      if (event.source !== frame.contentWindow) return;
      if (event.data?.type === "interactive-learning-diagram:ready") syncTheme(frame);
      if (event.data?.type === "interactive-learning-diagram:resize" && Number.isFinite(event.data.height)) {
        frame.style.height = `${Math.max(300, Math.min(4000, event.data.height + 2))}px`;
      }
    });
  });

  new MutationObserver(() => frames().forEach(syncTheme)).observe(document.documentElement, {
    attributes: true, attributeFilter: ["data-theme", "data-mode", "style"],
  });
  document.addEventListener("DOMContentLoaded", () => frames().forEach(frame => {
    frame.addEventListener("load", () => syncTheme(frame));
    syncTheme(frame);
  }));
})();
