(() => {
  const button = document.querySelector('.course-sidebar-toggle');
  if (!button || !document.getElementById('pst-primary-sidebar')) return;

  const storageKey = 'course-sidebar-collapsed';
  let collapsed = false;
  try {
    collapsed = localStorage.getItem(storageKey) === 'true';
  } catch {
    // The toggle also works when browser storage is unavailable.
  }

  function updateSidebar() {
    document.documentElement.classList.toggle('course-sidebar-collapsed', collapsed);
    button.setAttribute('aria-expanded', String(!collapsed));
    const label = collapsed ? 'Expand navigation sidebar' : 'Collapse navigation sidebar';
    button.setAttribute('aria-label', label);
    button.title = label;
  }

  updateSidebar();
  button.hidden = false;
  button.addEventListener('click', () => {
    collapsed = !collapsed;
    updateSidebar();
    try {
      localStorage.setItem(storageKey, String(collapsed));
    } catch {
      // Keep the current page interactive without persisting the preference.
    }
  });
})();
