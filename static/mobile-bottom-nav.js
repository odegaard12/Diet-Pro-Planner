/*
 * Diet Pro Planner v0.0.15.3
 * Simple mobile bottom navigation.
 *
 * No route ownership, no MutationObserver, no repeated DOM mutation.
 * It only clicks existing app menu buttons/links by visible text.
 */
(function () {
  'use strict';

  const MOBILE_QUERY = '(max-width: 760px), (pointer: coarse)';
  const mq = window.matchMedia(MOBILE_QUERY);

  const MAIN = [
    { id: 'summary', label: 'Resumen', icon: '🏠', match: ['resumen'] },
    { id: 'meals', label: 'Comidas', icon: '🍽️', match: ['registrar', 'comidas'] },
    { id: 'sport', label: 'Deporte', icon: '🏋️', match: ['deporte'] },
    { id: 'weight', label: 'Peso', icon: '⚖️', match: ['peso'] },
  ];

  const MORE = [
    { id: 'templates', label: 'Plantillas', icon: '⚡', match: ['plantillas'] },
    { id: 'foods', label: 'Alimentos', icon: '🥫', match: ['alimentos'] },
    { id: 'plan', label: 'Plan', icon: '📅', match: ['plan'] },
    { id: 'integrations', label: 'Integraciones', icon: '🔗', match: ['integraciones'] },
    { id: 'history', label: 'Historial', icon: '📚', match: ['historial'] },
  ];

  let built = false;

  function norm(value) {
    return String(value || '')
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function candidates() {
    return Array.from(document.querySelectorAll(
      'aside a, aside button, nav a, nav button, .sidebar a, .sidebar button, .side-nav a, .side-nav button, .nav-item, .tab, [role="tab"]'
    )).filter((el) => {
      if (!(el instanceof HTMLElement)) return false;
      if (el.closest('.dpp-mobile-nav, .dpp-mobile-more-sheet')) return false;

      const text = norm(el.textContent);
      if (!text) return false;

      const bad = [
        'actualizar',
        'exportar',
        'ir a hoy',
        '+ comida',
        '+ entreno',
        'guardar',
        'cancelar',
        'cerrar',
        'eliminar',
      ];
      if (bad.some((x) => text.includes(x))) return false;

      return [
        'resumen',
        'registrar',
        'comidas',
        'deporte',
        'plantillas',
        'alimentos',
        'plan',
        'peso',
        'integraciones',
        'historial',
      ].some((x) => text.includes(x));
    });
  }

  function findTarget(item) {
    const all = candidates();

    const scored = all.map((el) => {
      const text = norm(el.textContent);
      let score = 0;

      for (const key of item.match) {
        const k = norm(key);
        if (text === k) score += 100;
        else if (text.startsWith(k)) score += 60;
        else if (text.includes(k)) score += 30;
      }

      // Penaliza textos demasiado largos para evitar clicar tarjetas.
      score -= Math.max(0, text.length - 30) * 0.25;

      return { el, score, text };
    }).filter((x) => x.score > 0).sort((a, b) => b.score - a.score);

    return scored[0] ? scored[0].el : null;
  }

  function setActive(id) {
    document.querySelectorAll('[data-dpp-mobile-nav-id]').forEach((btn) => {
      const active = btn.getAttribute('data-dpp-mobile-nav-id') === id;
      btn.classList.toggle('is-active', active);
      btn.setAttribute('aria-current', active ? 'page' : 'false');
    });
  }

  function closeMore() {
    document.body.classList.remove('dpp-mobile-more-open');
  }

  function toggleMore() {
    document.body.classList.toggle('dpp-mobile-more-open');
  }

  function go(item) {
    const target = findTarget(item);
    setActive(item.id);
    closeMore();

    if (!target) {
      console.warn('[DPP mobile nav] target not found:', item.label);
      return;
    }

    target.click();

    try {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (_) {
      window.scrollTo(0, 0);
    }
  }

  function navButton(item, className) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = className;
    btn.setAttribute('data-dpp-mobile-nav-id', item.id);
    btn.innerHTML =
      '<span class="dpp-mobile-nav__icon">' + item.icon + '</span>' +
      '<span class="dpp-mobile-nav__label">' + item.label + '</span>';
    btn.addEventListener('click', function () {
      go(item);
    });
    return btn;
  }

  function build() {
    if (built || !mq.matches) return;

    document.body.classList.add('dpp-mobile-bottom-nav-enabled');

    const nav = document.createElement('nav');
    nav.className = 'dpp-mobile-nav';
    nav.setAttribute('aria-label', 'Navegación inferior móvil');

    MAIN.forEach((item) => nav.appendChild(navButton(item, 'dpp-mobile-nav__item')));

    const more = document.createElement('button');
    more.type = 'button';
    more.className = 'dpp-mobile-nav__item';
    more.setAttribute('data-dpp-mobile-nav-id', 'more');
    more.innerHTML =
      '<span class="dpp-mobile-nav__icon">☰</span>' +
      '<span class="dpp-mobile-nav__label">Más</span>';
    more.addEventListener('click', toggleMore);
    nav.appendChild(more);

    const backdrop = document.createElement('button');
    backdrop.type = 'button';
    backdrop.className = 'dpp-mobile-more-backdrop';
    backdrop.setAttribute('aria-label', 'Cerrar menú Más');
    backdrop.addEventListener('click', closeMore);

    const sheet = document.createElement('section');
    sheet.className = 'dpp-mobile-more-sheet';
    sheet.setAttribute('aria-label', 'Más secciones');
    sheet.innerHTML = '<div class="dpp-mobile-more-sheet__handle"></div><h2>Más secciones</h2>';

    const grid = document.createElement('div');
    grid.className = 'dpp-mobile-more-sheet__grid';
    MORE.forEach((item) => grid.appendChild(navButton(item, 'dpp-mobile-more-sheet__item')));
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

    setActive('summary');
    built = true;
  }

  function teardown() {
    if (mq.matches) return;
    document.querySelector('.dpp-mobile-nav')?.remove();
    document.querySelector('.dpp-mobile-more-backdrop')?.remove();
    document.querySelector('.dpp-mobile-more-sheet')?.remove();
    document.body.classList.remove('dpp-mobile-bottom-nav-enabled', 'dpp-mobile-more-open');
    built = false;
  }

  function init() {
    if (mq.matches) build();
    else teardown();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }

  if (mq.addEventListener) mq.addEventListener('change', init);
  else mq.addListener(init);
})();
