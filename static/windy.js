(() => {
  const dialog = document.getElementById('windy-dialog');
  const frame = document.getElementById('windy-frame');
  const open = document.getElementById('windy-open');
  open.addEventListener('click', () => {
    frame.src = frame.dataset.src;
    dialog.showModal();
  });
  document.getElementById('windy-close').addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => {
    frame.src = 'about:blank';
    open.focus();
  });
  dialog.addEventListener('click', event => {
    const rect = dialog.getBoundingClientRect();
    if (event.target === dialog && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) dialog.close();
  });
})();
