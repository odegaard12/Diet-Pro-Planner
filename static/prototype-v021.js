(() => {
  const buttons = document.querySelectorAll('[data-view]');
  const views = document.querySelectorAll('.view');

  function openView(name) {
    views.forEach(view => {
      view.classList.toggle('active-view', view.id === name);
    });

    buttons.forEach(button => {
      button.classList.toggle('active', button.dataset.view === name);
    });

    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  buttons.forEach(button => {
    button.addEventListener('click', () => openView(button.dataset.view));
  });
})();
