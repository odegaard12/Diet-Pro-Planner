/*
 * Diet Pro Planner · app shell helpers (classic script, loaded after app.js).
 * - window.DPP.registerPage(): add a page to the nav without monkeypatching render().
 * - Version comes from /health, targets from /api/profile (no hard-coded values).
 * - Logout button.
 */
(function () {
  'use strict';

  const pages = {};
  window.DPP_PAGE_TITLES = window.DPP_PAGE_TITLES || {};

  function registerPage(spec) {
    if (pages[spec.id]) return;
    pages[spec.id] = spec;
    window.DPP_PAGE_TITLES[spec.id] = spec.title || spec.label;
    UI5_NAV[spec.id] = [spec.icon, spec.label, spec.sub || ''];
    if (!PAGES.some((entry) => entry[0] === spec.id)) {
      const index = spec.after ? PAGES.findIndex((entry) => entry[0] === spec.after) : -1;
      PAGES.splice(index >= 0 ? index + 1 : PAGES.length, 0, [spec.id, spec.icon, spec.label]);
    }
  }

  // One wrapper for every registered page (instead of one per module).
  const baseRender = render;
  render = function () {
    const spec = pages[page];
    if (!spec) return baseRender.apply(this, arguments);
    setTitle(spec.title || spec.label);
    document.body.classList.remove('fi13-home');
    spec.render();
    setTimeout(ui5ApplyShell, 0);
  };
  window.render = render;

  async function loadProfile() {
    try {
      const data = await api('/api/profile');
      window.DPP_PROFILE = data;
      const p = data.computed?.protein;
      const profile = data.profile || {};
      const ruleProtein = document.getElementById('ruleProtein');
      if (ruleProtein && p) ruleProtein.textContent = `${p.goal_min_g}–${p.max_g} g/día`;
      const ruleOil = document.getElementById('ruleOil');
      if (ruleOil && profile.oil_normal_g !== undefined) ruleOil.textContent = `${fmt(profile.oil_normal_g)} g normal · ${fmt(profile.oil_max_g)} g máximo`;
      document.dispatchEvent(new CustomEvent('dpp:profile', {detail: data}));
      return data;
    } catch (e) {
      return null;
    }
  }

  async function loadVersion() {
    try {
      const r = await fetch('/health', {cache: 'no-store'});
      const data = await r.json();
      window.DPP_VERSION = data.version || '';
      document.title = `Diet Pro Planner · ${window.DPP_VERSION}`;
      ui5ApplyShell();
    } catch (e) { /* offline */ }
  }

  function addLogout() {
    const actions = document.querySelector('.top-actions');
    if (!actions || document.getElementById('btnLogout')) return;
    const btn = document.createElement('button');
    btn.id = 'btnLogout'; btn.className = 'ghost'; btn.type = 'button'; btn.textContent = 'Salir';
    btn.title = 'Cerrar sesión en este dispositivo';
    btn.onclick = async () => {
      if (!confirm('¿Cerrar sesión en este dispositivo?')) return;
      try {
        // Drop the offline copy of the data on this device too.
        if (window.caches) await Promise.all((await caches.keys()).filter((k) => k.startsWith('dpp-')).map((k) => caches.delete(k)));
        await fetch('/api/auth/logout', {method: 'POST', credentials: 'same-origin'});
      } finally { location.reload(); }
    };
    actions.appendChild(btn);
  }

  window.DPP = {registerPage, loadProfile, pages};
  addLogout();
  loadVersion();
  loadProfile();
})();
