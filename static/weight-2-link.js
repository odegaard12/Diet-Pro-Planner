(function () {
  'use strict';

  const TARGET_TEXT = 'Detalle completo en Peso 2.0 próximamente.';
  const LINK_ID = 'dppWeight2InlineLink';

  function makeLink() {
    const wrap = document.createElement('div');
    wrap.className = 'dpp-weight2-cta';
    wrap.id = LINK_ID;
    wrap.innerHTML = `
      <a href="/weight-2" class="dpp-weight2-button">
        <span>Ver Peso 2.0</span>
        <strong>Tendencias completas →</strong>
      </a>
    `;
    return wrap;
  }

  function enhanceBodyCard() {
    if (document.getElementById(LINK_ID)) return true;

    const nodes = Array.from(document.querySelectorAll('p, small, div, span'));
    const target = nodes.find((node) => {
      const text = (node.textContent || '').trim();
      return text.includes(TARGET_TEXT) || text.includes('Peso 2.0 próximamente');
    });

    if (!target) return false;

    target.textContent = 'Detalle completo disponible en Peso 2.0.';
    target.insertAdjacentElement('afterend', makeLink());
    return true;
  }

  function addBottomNavDeepLink() {
    const morePanel = document.querySelector('.mobile-more-panel, .dpp-mobile-more, [data-mobile-more]');
    if (!morePanel || document.getElementById('dppWeight2MoreLink')) return;

    const a = document.createElement('a');
    a.id = 'dppWeight2MoreLink';
    a.href = '/weight-2';
    a.className = 'dpp-weight2-more-link';
    a.innerHTML = '<span>📉</span><strong>Peso 2.0</strong><small>Composición y tendencias</small>';
    morePanel.appendChild(a);
  }

  function run() {
    enhanceBodyCard();
    addBottomNavDeepLink();
  }

  document.addEventListener('DOMContentLoaded', run);
  window.addEventListener('load', run);

  const observer = new MutationObserver(run);
  observer.observe(document.documentElement, { childList: true, subtree: true });

  setTimeout(run, 500);
  setTimeout(run, 1500);
  setTimeout(run, 3000);
})();
