/*
 * Diet Pro Planner v0.0.15.2
 * Mobile bottom navigation.
 *
 * This file mirrors existing app navigation. It does not own routes/state.
 */
(function () {
  'use strict';

  const MOBILE_QUERY = '(max-width: 760px), (pointer: coarse)';
  const mq = window.matchMedia(MOBILE_QUERY);

  const MAIN_ITEMS = [
    { id: 'summary', label: 'Resumen', icon: '🏠', keys: ['resumen', 'panel diario'] },
    { id: 'meals', label: 'Comidas', icon: '🍽️', keys: ['registrar', 'comidas'] },
    { id: 'sport', label: 'Deporte', icon: '🏋️', keys: ['deporte', 'strava', 'manual'] },
    { id: 'weight', label: 'Peso', icon: '⚖️', keys: ['peso', 'historial de peso'] },
  ];

  const MORE_ITEMS = [
    { id: 'templates', label: 'Plantillas', icon: '⚡', keys: ['plantillas', '2 clics'] },
    { id: 'foods', label: 'Alimentos', icon: '🥫', keys: ['alimentos', 'productos', 'ocr'] },
    { id: 'plan', label: 'Plan', icon: '📅', keys: ['plan', 'semana'] },
    { id: 'integrations', label: 'Integraciones', icon: '🔗', keys: ['integraciones', 'strava'] },
    { id: 'history', label: 'Historial', icon: '📚', keys: ['historial', 'todo'] },
  ];

  let actions = new Map();
  let activeId = 'summary';
  let built = false;

  function normalize(text) {
    return String(text || '')
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function isAppNavElement(el) {
    if (!el || !(el instanceof HTMLElement)) return false;

    const text = normalize(el.textContent);
    if (!text || text.length < 3) return false;

    const bad = [
      'actualizar',
      'exportar db',
      'ir a hoy real',
      '+ comida',
      '+ entreno',
      'guardar',
      'cancelar',
      'eliminar',
      'borrar',
    ];
    if (bad.some((x) => text.includes(x))) return false;

    const navRoot = el.closest('aside, nav, .sidebar, .side-nav, .nav-rail, [class*="sidebar"], [class*="nav"]');
    if (!navRoot) return false;

    const wanted = [
      'resumen', 'registrar', 'comidas', 'deporte', 'strava', 'plantillas',
      'alimentos', 'productos', 'ocr', 'plan', 'semana', 'peso',
      'integraciones', 'historial',
    ];
    return wanted.some((x) => text.includes(x));
  }

  function scanActions() {
    const next = new Map();
    const selectors = [
      'aside a',
      'aside button',
      'nav a',
      'nav button',
      '.sidebar a',
      '.sidebar button',
      '.side-nav a',
      '.side-nav button',
      '.nav-rail a',
      '.nav-rail button',
      '[class*="sidebar"] a',
      '[class*="sidebar"] button',
      '[class*="nav"] a',
      '[class*="nav"] button',
    ];

    const candidates = Array.from(document.querySelectorAll(selectors.join(','))).filter(isAppNavElement);

    function findFor(item) {
      const scored = candidates
        .map((el) => {
          const text = normalize(el.textContent);
          let score = 0;
          for (const key of item.keys) {
            const k = normalize(key);
            if (text.includes(k)) score += k.length;
          }
          if (el.getAttribute('aria-current') || el.className.toString().includes('active')) score += 3;
          return { el, score, text };
        })
        .filter((x) => x.score > 0)
        .sort((a, b) => b.score - a.score);

      return scored[0] ? scored[0].el : null;
    }

    for (const item of [...MAIN_ITEMS, ...MORE_ITEMS]) {
      const el = findFor(item);
      if (el) next.set(item.id, el);
    }

    actions = next;
    return next;
  }

  function clickAction(id) {
    const el = actions.get(id) || scanActions().get(id);
    if (!el) return false;

    activeId = id;
    closeMore();
    updateActive();

    try {
      el.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    } catch (_) {
      // ignore
    }

    el.click();
    window.setTimeout(updateActiveFromSource, 120);
    return true;
  }

  function updateActiveFromSource() {
    for (const item of [...MAIN_ITEMS, ...MORE_ITEMS]) {
      const el = actions.get(item.id);
      if (!el) continue;
      const cls = String(el.className || '').toLowerCase();
      const current = el.getAttribute('aria-current');
      if (current || cls.includes('active') || cls.includes('selected')) {
        activeId = item.id;
        updateActive();
        return;
      }
    }

    const h = normalize(document.querySelector('h1,h2,.page-title,.section-title')?.textContent || '');
    if (h.includes('peso')) activeId = 'weight';
    else if (h.includes('deporte') || h.includes('strava')) activeId = 'sport';
    else if (h.includes('registrar') || h.includes('comida')) activeId = 'meals';
    else if (h.includes('resumen') || h.includes('dashboard')) activeId = 'summary';

    updateActive();
  }

  function updateActive() {
    document.querySelectorAll('[data-dpp-mobile-nav-id]').forEach((btn) => {
      const id = btn.getAttribute('data-dpp-mobile-nav-id');
      const isActive = id === activeId;
      btn.classList.toggle('is-active', isActive);
      btn.setAttribute('aria-current', isActive ? 'page' : 'false');
    });
  }

  function openMore() {
    document.body.classList.add('dpp-mobile-more-open');
    const sheet = document.querySelector('.dpp-mobile-more-sheet');
    if (sheet) sheet.setAttribute('aria-hidden', 'false');
  }

  function closeMore() {
    document.body.classList.remove('dpp-mobile-more-open');
    const sheet = document.querySelector('.dpp-mobile-more-sheet');
    if (sheet) sheet.setAttribute('aria-hidden', 'true');
  }

  function buttonFor(item, extraClass) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = extraClass || 'dpp-mobile-nav__item';
    btn.setAttribute('data-dpp-mobile-nav-id', item.id);
    btn.innerHTML = `<span class="dpp-mobile-nav__icon">${item.icon}</span><span class="dpp-mobile-nav__label">${item.label}</span>`;
    btn.addEventListener('click', () => clickAction(item.id));
    return btn;
  }

  function build() {
    if (built) return;
    if (!mq.matches) return;

    scanActions();

    const nav = document.createElement('nav');
    nav.className = 'dpp-mobile-nav';
    nav.setAttribute('aria-label', 'Navegación principal móvil');

    for (const item of MAIN_ITEMS) {
      nav.appendChild(buttonFor(item));
    }

    const moreBtn = document.createElement('button');
    moreBtn.type = 'button';
    moreBtn.className = 'dpp-mobile-nav__item';
    moreBtn.setAttribute('data-dpp-mobile-nav-id', 'more');
    moreBtn.innerHTML = '<span class="dpp-mobile-nav__icon">☰</span><span class="dpp-mobile-nav__label">Más</span>';
    moreBtn.addEventListener('click', () => {
      if (document.body.classList.contains('dpp-mobile-more-open')) closeMore();
      else openMore();
    });
    nav.appendChild(moreBtn);

    const backdrop = document.createElement('button');
    backdrop.type = 'button';
    backdrop.className = 'dpp-mobile-more-backdrop';
    backdrop.setAttribute('aria-label', 'Cerrar más navegación');
    backdrop.addEventListener('click', closeMore);

    const sheet = document.createElement('section');
    sheet.className = 'dpp-mobile-more-sheet';
    sheet.setAttribute('aria-hidden', 'true');
    sheet.innerHTML = '<div class="dpp-mobile-more-sheet__handle"></div><h2>Más secciones</h2>';

    const grid = document.createElement('div');
    grid.className = 'dpp-mobile-more-sheet__grid';
    for (const item of MORE_ITEMS) {
      grid.appendChild(buttonFor(item, 'dpp-mobile-more-sheet__item'));
    }
    sheet.appendChild(grid);

    const close = document.createElement('button');
    close.type = 'button';
    close.className = 'dpp-mobile-more-sheet__close';
    close.textContent = 'Cerrar';
    close.addEventListener('click', closeMore);
    sheet.appendChild(close);

    document.body.appendChild(backdrop);
    document.body.appendChild(sheet);
    document.body.appendChild(nav);
    document.body.classList.add('dpp-mobile-bottom-nav-enabled');

    built = true;
    updateActiveFromSource();

    document.addEventListener('keydown', (ev) => {
      if (ev.key === 'Escape') closeMore();
    });
  }

  function destroyIfDesktop() {
    if (mq.matches) return;
    document.querySelector('.dpp-mobile-nav')?.remove();
    document.querySelector('.dpp-mobile-more-backdrop')?.remove();
    document.querySelector('.dpp-mobile-more-sheet')?.remove();
    document.body.classList.remove('dpp-mobile-bottom-nav-enabled', 'dpp-mobile-more-open');
    built = false;
  }

  function init() {
    if (mq.matches) build();
    else destroyIfDesktop();
  }

  const observer = new MutationObserver(() => {
    if (!mq.matches) return;
    scanActions();
    updateActiveFromSource();
  });

  window.addEventListener('DOMContentLoaded', () => {
    init();
    observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['class', 'aria-current'] });
    window.setTimeout(init, 300);
    window.setTimeout(init, 900);
  });

  if (mq.addEventListener) mq.addEventListener('change', init);
  else mq.addListener(init);
})();
