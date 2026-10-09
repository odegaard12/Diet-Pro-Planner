/**
 * v0.0.15 workout card renderer bridge.
 *
 * Classic JS bridge for legacy static/app.js.
 * Keep this file small and focused.
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

  // Imported notes carry the provider's internal activity id ("… · id=123"): not useful on screen.
  function cleanNote(note) {
    return String(note || '').replace(/\s*·?\s*\bid=\d+\b/g, '').trim();
  }

  function workoutSummary(workout) {
    const parts = [`${fmtNumber(workout.minutes)} min`];

    if (workout.distance_km) {
      parts.push(`${fmtNumber(workout.distance_km)} km`);
    }

    const note = cleanNote(workout.notes);
    if (note) {
      parts.push(escapeHtml(note));
    }

    return parts.join(' · ');
  }

  function workoutCardCompact(workout) {
    const id = Number(workout.id);

    return `
      <article class="compact-card workout">
        <div class="compact-head">
          <div>
            <b>${escapeHtml(workout.time)} · ${escapeHtml(workout.name)}</b>
            <small>${workoutSummary(workout)}</small>
          </div>
          <strong>${fmtNumber(workout.kcal)} kcal</strong>
          <button class="mini-delete" title="Borrar" onclick="deleteWorkout(${id})">×</button>
        </div>
      </article>`;
  }

  window.DPPDashboardWorkoutCard = {
    cleanNote,
    workoutSummary,
    workoutCardCompact,
  };
})();
