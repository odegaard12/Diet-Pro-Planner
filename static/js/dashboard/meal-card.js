/**
 * Meal card rendering helpers.
 * Keep card components small and testable.
 */

import { escapeHtml, fmtKcal, fmtNumber } from '../core/format.js';

export function itemSummary(items) {
  const list = items || [];
  const shown = list.slice(0, 3).map((item) => {
    const name = escapeHtml(item.food_name || item.name || '');
    return `${name} ${fmtNumber(item.grams)}g`;
  });
  const extra = list.length > 3 ? ` +${list.length - 3}` : '';
  return shown.join(' · ') + extra;
}

export function cleanTechnicalNote(note) {
  return String(note || '').replace(/\b(?:REAL|PLAN)_\d{4}_[A-Z0-9_]+\s*-\s*/g, '');
}

export function mealCardCompact(meal) {
  const totals = meal.totals || {};
  const note = cleanTechnicalNote(meal.notes);
  return `
    <article class="compact-card meal">
      <div class="compact-head">
        <div>
          <b>${escapeHtml(meal.time)} · ${escapeHtml(meal.name)}</b>
          <small>${itemSummary(meal.items)}</small>
        </div>
        <strong>${fmtKcal(totals.kcal)}<br><span>${fmtNumber(totals.protein)} g prot.</span></strong>
        <button class="mini-delete" title="Borrar" onclick="deleteMeal(${Number(meal.id)})">×</button>
      </div>
      ${note ? `<p class="compact-note">${escapeHtml(note)}</p>` : ''}
    </article>`;
}
