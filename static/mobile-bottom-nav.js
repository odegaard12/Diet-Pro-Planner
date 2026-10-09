/*
 * Diet Pro Planner · phone bottom bar (v0.3.8).
 * The same five sections as the desktop sidebar (window.DPP_NAV from app.js); pages inside a
 * section are tabs at the top of the view, so there is no "Más" sheet any more.
 */
(function () {
  'use strict';

  const mq = window.matchMedia('(max-width: 760px), (pointer: coarse)');
  let built = false;

  function setActive() {
    const nav = window.DPP_NAV;
    if (!nav) return;
    const cur = nav.sectionOf(typeof page === 'string' ? page : 'home');
    document.querySelectorAll('[data-dpp-section]').forEach((btn) => {
      const active = btn.dataset.dppSection === cur.id;
      btn.classList.toggle('is-active', active);
      btn.setAttribute('aria-current', active ? 'page' : 'false');
    });
  }

  function build() {
    const nav = window.DPP_NAV;
    if (built || !mq.matches || !nav) return;
    document.body.classList.add('dpp-mobile-bottom-nav-enabled');
    const bar = document.createElement('nav');
    bar.className = 'dpp-mobile-nav';
    bar.setAttribute('aria-label', 'Secciones');
    nav.sections.forEach((s) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'dpp-mobile-nav__item';
      btn.dataset.dppSection = s.id;
      btn.innerHTML = '<span class="dpp-mobile-nav__icon">' + nav.navIcon(s.icon) + '</span><span class="dpp-mobile-nav__label">' + s.label + '</span>';
      btn.addEventListener('click', () => window.go(s.tabs[0][0]));
      bar.appendChild(btn);
    });
    document.body.appendChild(bar);
    built = true;
    setActive();
  }

  function teardown() {
    if (mq.matches) return;
    document.querySelector('.dpp-mobile-nav')?.remove();
    document.body.classList.remove('dpp-mobile-bottom-nav-enabled');
    built = false;
  }

  function init() { if (mq.matches) build(); else teardown(); }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once: true});
  else init();
  document.addEventListener('dpp:page', setActive);
  if (mq.addEventListener) mq.addEventListener('change', init); else mq.addListener(init);
})();
