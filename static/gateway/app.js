(() => {
  const body = document.body;
  const toggle = document.querySelector('[data-sidebar-toggle]');
  const overlay = document.querySelector('[data-sidebar-overlay]');
  const closeSidebar = () => body.classList.remove('sidebar-open');
  toggle?.addEventListener('click', () => body.classList.toggle('sidebar-open'));
  overlay?.addEventListener('click', closeSidebar);
  document.querySelectorAll('.sidebar-nav a').forEach((link) => link.addEventListener('click', closeSidebar));

  document.querySelectorAll('[data-copy]').forEach((button) => {
    button.addEventListener('click', async () => {
      const target = document.querySelector(button.dataset.copy);
      if (!target) return;
      const value = target.value ?? target.textContent ?? '';
      try {
        await navigator.clipboard.writeText(value.trim());
        const original = button.dataset.label || button.textContent.trim();
        button.dataset.label = original;
        button.classList.add('copied');
        button.querySelector('[data-copy-label]')?.replaceChildren('Copied');
        setTimeout(() => {
          button.classList.remove('copied');
          button.querySelector('[data-copy-label]')?.replaceChildren(original);
        }, 1400);
      } catch (_error) {
        window.prompt('Copy this value:', value.trim());
      }
    });
  });

  document.querySelectorAll('[data-tab-group]').forEach((group) => {
    const buttons = group.querySelectorAll('[data-tab]');
    const panels = group.querySelectorAll('[data-tab-panel]');
    buttons.forEach((button) => button.addEventListener('click', () => {
      const selected = button.dataset.tab;
      buttons.forEach((item) => item.classList.toggle('active', item === button));
      panels.forEach((panel) => panel.hidden = panel.dataset.tabPanel !== selected);
    }));
  });

  document.querySelectorAll('[data-dismiss]').forEach((button) => {
    button.addEventListener('click', () => button.closest('.flash')?.remove());
  });
})();
