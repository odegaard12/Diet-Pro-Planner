/**
 * Shared formatting helpers for Diet Pro Planner.
 * Keep this file small. Move only generic formatting here.
 */

export function fmtNumber(value, maximumFractionDigits = 1) {
  return Number(value || 0).toLocaleString('es-ES', { maximumFractionDigits });
}

export function fmtKcal(value) {
  return `${fmtNumber(value, 1)} kcal`;
}

export function fmtProtein(value) {
  return `${fmtNumber(value, 1)} g proteína`;
}

export function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}
