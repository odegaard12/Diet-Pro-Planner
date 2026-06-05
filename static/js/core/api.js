/**
 * Shared API helpers for Diet Pro Planner.
 */

export async function apiJson(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });

  if (!response.ok) {
    let message = 'Error';
    try {
      const payload = await response.json();
      message = payload.error || message;
    } catch {
      // keep generic message
    }
    throw new Error(message);
  }

  return response.json();
}
