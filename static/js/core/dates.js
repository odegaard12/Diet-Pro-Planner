/**
 * Shared date helpers for Diet Pro Planner.
 */

export function todayIso(state) {
  return state?.today || new Date().toISOString().slice(0, 10);
}

export function selectedDay(selectedDate, state) {
  return selectedDate || todayIso(state);
}

export function isToday(dateValue, state) {
  return dateValue === todayIso(state);
}
