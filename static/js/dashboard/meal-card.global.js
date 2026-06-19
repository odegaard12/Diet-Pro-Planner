/**
 * v0.0.15 meal card renderer bridge.
 *
 * This file is intentionally classic JS, not ESM, because legacy static/app.js
 * is still loaded as a classic script. Keep this file small and focused.
 */
(function () {
  'use strict';

  function fmtNumber(value, maximumFractionDigits) {
    return Number(value || 0).toLocaleString('es-ES', {
      maximumFractionDigits: maximumFractionDigits ?? 1,
    });
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function cleanTechnicalNote(note) {
    return String(note || '').replace(/\b(?:REAL|PLAN)_\d{4}_[A-Z0-9_]+\s*-\s*/g, '');
  }

  function itemName(item) {
    return item.food_name || item.name || '';
  }

  function itemSummary(items) {
    const list = Array.isArray(items) ? items : [];
    const shown = list.slice(0, 3).map((item) => {
      return `${escapeHtml(itemName(item))} ${fmtNumber(item.grams)}g`;
    });
    const extra = list.length > 3 ? ` +${list.length - 3}` : '';
    return shown.join(' · ') + extra;
  }

  function mealCardCompact(meal) {
    const totals = meal.totals || {};
    const note = cleanTechnicalNote(meal.notes);
    const id = Number(meal.id);

    return `
      <article class="compact-card meal">
        <div class="compact-head">
          <div>
            <b>${escapeHtml(meal.time)} · ${escapeHtml(meal.name)}</b>
            <small>${itemSummary(meal.items)}</small>
          </div>
          <strong>${fmtNumber(totals.kcal)} kcal<br><span>${fmtNumber(totals.protein)} g prot.</span></strong>
          <button class="mini-delete" title="Borrar" onclick="deleteMeal(${id})">×</button>
        </div>
        ${note ? `<p class="compact-note">${escapeHtml(note)}</p>` : ''}
      </article>`;
  }

  window.DPPDashboardMealCard = {
    cleanTechnicalNote,
    itemSummary,
    mealCardCompact,
  };
})();
