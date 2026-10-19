/* Historial (v0.5.0): one timeline grouped by day, with friendly dates and daily totals. */
(function () {
  'use strict';

  const DAYS_PER_PAGE = 7;
  let shown = DAYS_PER_PAGE;

  /** "Hoy", "Ayer" or "lun 19 oct" (with the year when it is not the current one). */
  window.friendlyDate = function (iso) {
    if (!iso) return '';
    const d = new Date(iso + 'T12:00:00');
    const t = new Date(today() + 'T12:00:00');
    const diff = Math.round((t - d) / 86400000);
    if (diff === 0) return 'Hoy';
    if (diff === 1) return 'Ayer';
    const opts = {weekday: 'short', day: 'numeric', month: 'short'};
    if (d.getFullYear() !== t.getFullYear()) opts.year = 'numeric';
    return d.toLocaleDateString('es-ES', opts).replace(/\./g, '');
  };

  function mealRow(m) {
    const items = (m.items || []).map((i) => `<span class="chip">${esc(i.food_name)} ${fmt(i.grams)} g</span>`).join('');
    return `<div class="hist-row"><time>${esc(m.time || '')}</time><div class="hist-main"><b>${esc(m.name || 'Comida')}</b><span class="hist-kcal">${fmt(m.totals?.kcal || 0)} kcal · ${fmt(m.totals?.protein || 0)} g prot</span>
      ${items ? `<div class="chips">${items}</div>` : ''}${m.notes ? `<p class="muted">${esc(m.notes)}</p>` : ''}</div>
      <div class="hist-actions"><button class="icon-btn" type="button" aria-label="Repetir hoy" title="Repetir hoy" onclick="repeatMeal(${Number(m.id)}, this)">↻</button><button class="icon-btn" type="button" aria-label="Borrar comida" onclick="deleteMeal(${Number(m.id)})">×</button></div></div>`;
  }

  function workoutRow(w) {
    const bits = [`${fmt(w.minutes)} min`, Number(w.distance_km) > 0 ? `${fmt(w.distance_km)} km` : '', `${fmt(w.kcal)} kcal`].filter(Boolean).join(' · ');
    const note = cleanWorkoutNote(w.notes);
    return `<div class="hist-row sport"><time>${esc(w.time || '')}</time><div class="hist-main"><b>${esc(w.name || 'Entreno')}</b><span class="hist-kcal">${bits}</span>${note ? `<p class="muted">${esc(note)}</p>` : ''}</div>
      <div class="hist-actions"><button class="icon-btn" type="button" aria-label="Borrar entreno" onclick="deleteWorkout(${Number(w.id)})">×</button></div></div>`;
  }

  function dayCard(date, meals, workouts) {
    const kcal = meals.reduce((a, m) => a + (m.totals?.kcal || 0), 0);
    const prot = meals.reduce((a, m) => a + (m.totals?.protein || 0), 0);
    const burn = workouts.reduce((a, w) => a + Number(w.kcal || 0), 0);
    const rows = [...meals.map((m) => [m.time || '', mealRow(m)]), ...workouts.map((w) => [w.time || '', workoutRow(w)])]
      .sort((a, b) => a[0].localeCompare(b[0])).map((r) => r[1]).join('');
    return `<section class="card hist-day"><header><h3>${esc(window.friendlyDate(date))}</h3>
      <span class="hist-total"><b>${fmt(kcal)}</b> kcal · <b>${fmt(prot)}</b> g prot${burn ? ` · <span class="good">+${fmt(burn)} entreno</span>` : ''}</span></header>${rows}</section>`;
  }

  window.renderHistory = function () {
    const days = new Map();
    const slot = (d) => { if (!days.has(d)) days.set(d, {meals: [], workouts: []}); return days.get(d); };
    state.meals.forEach((m) => slot(m.date).meals.push(m));
    state.workouts.forEach((w) => slot(w.date).workouts.push(w));
    const dates = [...days.keys()].sort().reverse();
    const more = dates.length > shown
      ? `<button class="btn secondary more-btn" type="button" onclick="window.dppHistoryMore()">Ver días anteriores (${dates.length - shown})</button>` : '';
    $('#view').innerHTML = dates.length
      ? `<p class="muted hist-lead">${state.meals.length} comidas y ${state.workouts.length} entrenos · ↻ repite una comida hoy</p>`
        + dates.slice(0, shown).map((d) => dayCard(d, days.get(d).meals, days.get(d).workouts)).join('') + more
      : '<div class="empty">Todavía no hay nada registrado. Empieza por Comidas › Registrar.</div>';
  };
  window.dppHistoryMore = () => { shown += DAYS_PER_PAGE; window.renderHistory(); };
})();
