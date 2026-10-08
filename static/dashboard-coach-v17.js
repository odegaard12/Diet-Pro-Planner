/*
 * Smart Coach for the home view. Renders into #coachSlot (created by home.js).
 * Keeps the .dpp-coach-* classes and the dpp:coach-rendered event that
 * pantry-v019.js uses to add its "No tengo esto / Otra comida / Despensa" actions.
 */
(function () {
  'use strict';

  const ENDPOINT = '/api/smart-coach/day';
  let busy = false;

  const chip = (label, value) => `<span class="dpp-coach-chip"><b>${esc(value)}</b><small>${esc(label)}</small></span>`;

  function render(slot, data) {
    const c = data.coach || {};
    const next = c.next_meal || {}, messages = c.messages || {}, pantry = c.pantry || {};
    const used = Array.isArray(pantry.used) ? pantry.used : [];
    const avoid = Array.isArray(next.avoid) ? next.avoid.filter(Boolean) : [];
    const flags = Array.isArray(c.flags) ? c.flags : [];
    const sub = slot.querySelector('header p');
    if (sub && c.headline) sub.textContent = c.headline;
    slot.querySelector('.coach-body').innerHTML = `
      <div class="dpp-coach-visual">
        <div class="dpp-coach-main">
          <div class="dpp-coach-label">MEJOR COMIDA AHORA</div>
          <div class="dpp-coach-decision">${esc(next.primary || 'Registra comida real para afinar la recomendación.')}</div>
          <div class="dpp-coach-why">${esc(next.why || '')}</div>
        </div>
        <div class="dpp-coach-grid">
          <div class="dpp-coach-box"><span>💪</span><b>Proteína</b><small>${esc(messages.protein || 'Prioriza proteína útil.')}</small></div>
          <div class="dpp-coach-box"><span>⚡</span><b>Recuperación</b><small>${esc(messages.biocharge || 'Sin dato de recuperación.')}</small></div>
          <div class="dpp-coach-box"><span>🧠</span><b>Contexto</b><small>${esc(messages.yesterday || 'Sin señales fuertes de ayer.')}</small></div>
        </div>
        ${used.length ? `<div class="dpp-coach-row">${chip('despensa', used.join(' · '))}</div>` : ''}
        ${avoid.length ? `<div class="dpp-coach-avoid"><b>Evita ahora:</b> ${esc(avoid.join(' · '))}</div>` : ''}
        ${flags.length ? `<div class="dpp-coach-signals">Señales: ${flags.map(esc).join(' · ')}</div>` : ''}
      </div>`;
  }

  async function load(forDate) {
    const slot = document.getElementById('coachSlot');
    if (!slot || busy) return;
    busy = true;
    const date = typeof forDate === 'string' && forDate ? forDate : day();
    try {
      const res = await fetch(`${ENDPOINT}?date=${encodeURIComponent(date)}`, {credentials: 'same-origin', cache: 'no-store'});
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (!document.body.contains(slot)) return;
      render(slot, data);
      document.dispatchEvent(new CustomEvent('dpp:coach-rendered', {detail: data}));
    } catch (err) {
      const body = slot.querySelector('.coach-body');
      if (body && !body.querySelector('.dpp-coach-error')) body.insertAdjacentHTML('beforeend', `<div class="dpp-coach-avoid dpp-coach-error">No se pudo cargar el Coach: ${esc(err.message || err)}</div>`);
    } finally {
      busy = false;
    }
  }

  document.addEventListener('click', (ev) => {
    if (ev.target.closest('[data-coach-refresh]')) { ev.preventDefault(); load(); }
  });

  // Called by static/js/features/home.js right after the home view renders.
  window.DPPCoachV17 = {load};
})();
