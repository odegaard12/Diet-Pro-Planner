/* Diet Pro Planner v0.0.21 · visual runtime */
(() => {
  'use strict';
  if (window.__DPP_V021_RUNTIME__) return;
  window.__DPP_V021_RUNTIME__ = true;

  const VERSION = 'v0.0.21-dev';
  const NAV = {
    home: ['⌂', 'Hoy'],
    register: ['＋', 'Registrar'],
    sport: ['◇', 'Deporte'],
    activityPlan: ['▦', 'Plan deporte'],
    'activity-plan': ['▦', 'Plan deporte'],
    templates: ['✦', 'Plantillas'],
    foods: ['▣', 'Alimentos'],
    pantry: ['◫', 'Despensa'],
    plan: ['□', 'Plan'],
    weights: ['↗', 'Peso'],
    integrations: ['⌁', 'Integraciones'],
    history: ['≡', 'Historial']
  };

  function dateLabel() {
    try {
      const value = new Intl.DateTimeFormat('es-ES', {
        weekday: 'long', day: 'numeric', month: 'long'
      }).format(new Date());
      return value.charAt(0).toUpperCase() + value.slice(1);
    } catch (_) {
      return 'Diet Pro Planner';
    }
  }

  function syncNav() {
    document.querySelectorAll('#nav [data-page]').forEach(button => {
      const key = button.dataset.page || '';
      const fallback = (button.textContent || key).replace(/^\s*\S+\s*/, '').trim() || key;
      const [icon, label] = NAV[key] || ['•', fallback];
      button.innerHTML = `<span class="v021-nav-icon">${icon}</span><span class="v021-nav-label">${label}</span>`;
      button.setAttribute('aria-label', label);
    });
  }

  function syncHeader() {
    document.body.classList.add('dpp-v021');
    document.title = `Diet Pro Planner · ${VERSION}`;

    const eyebrow = document.querySelector('.eyebrow');
    const title = document.querySelector('#pageTitle');
    const currentPage = typeof window.page === 'string' ? window.page : '';

    if (eyebrow) eyebrow.textContent = currentPage === 'home' ? dateLabel() : `Diet Pro Planner · ${VERSION}`;
    if (title && currentPage === 'home') title.textContent = 'Buenos días, Óscar';

    const badge = document.querySelector('#ui5Badge');
    if (badge) badge.remove();
  }

  function sync() {
    syncHeader();
    syncNav();
  }

  function wrapGlobal(name) {
    const original = window[name];
    if (typeof original !== 'function' || original.__dppV021Wrapped) return;
    const wrapped = function () {
      const result = original.apply(this, arguments);
      requestAnimationFrame(sync);
      return result;
    };
    wrapped.__dppV021Wrapped = true;
    window[name] = wrapped;
    try { eval(`${name} = window[name]`); } catch (_) {}
  }

  ['renderNav', 'render', 'setTitle', 'go'].forEach(wrapGlobal);
  document.addEventListener('click', () => requestAnimationFrame(sync));

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', sync, { once: true });
  } else {
    sync();
  }
})();
