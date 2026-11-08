(() => {
  'use strict';

  const form = document.querySelector('[data-obs-form]');
  const preview = document.querySelector('[data-obs-preview]');
  const source = document.querySelector('[data-obs-url]');
  const open = document.querySelector('[data-obs-open]');
  const status = document.querySelector('[data-obs-copy-status]');
  const base = new URL(open.href);
  new ResizeObserver(([entry]) => {
    preview.style.transform = `scale(${entry.contentRect.width / 640})`;
  }).observe(preview.parentElement);

  function update(loadPreview) {
    const url = new URL(base);
    new FormData(form).forEach((value, key) => url.searchParams.set(key, value));
    source.value = url.href;
    open.href = url.href;
    if (loadPreview) preview.src = url.href;
    status.textContent = '';
  }

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    update(true);
  });
  document.querySelector('[data-obs-copy]').addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(source.value);
      status.textContent = 'URL copied.';
    } catch {
      source.focus();
      source.select();
      status.textContent = 'Press Ctrl+C to copy the selected URL.';
    }
  });
  update(false);
})();
