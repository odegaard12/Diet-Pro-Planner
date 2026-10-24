/* First-run guide for "Hoy" (v0.5.5): three steps that tick themselves off; hidden once the app is in use. */
(function () {
  'use strict';

  const KEY = 'dppWelcomeDismissed';
  const dismissed = () => { try { return localStorage.getItem(KEY) === '1'; } catch (e) { return false; } };

  function steps() {
    const p = window.DPP_PROFILE?.profile || {};
    return [
      {done: !!(p.birth_year && p.sex), title: 'Cuéntanos de ti', hint: 'Sexo, año de nacimiento y altura afinan tus calorías y tu proteína.', page: 'goals', cta: 'Abrir Ajustes'},
      {done: (state.weights || []).length > 0, title: 'Registra tu peso', hint: 'Con dos pesos oficiales aparece tu tendencia.', page: 'weights', cta: 'Registrar peso'},
      {done: (state.meals || []).length > 0, title: 'Añade tu primera comida', hint: 'Busca un alimento (o pega su código de barras) y ajusta los gramos.', page: 'register', cta: 'Añadir comida'},
    ];
  }

  function html() {
    if (dismissed() || (state.meals || []).length >= 3) return '';
    const list = steps();
    if (list.every((s) => s.done)) return '';
    const next = list.findIndex((s) => !s.done);
    const items = list.map((s, i) => `<li class="${s.done ? 'done' : i === next ? 'next' : ''}"><span class="welcome-n" aria-hidden="true">${s.done ? '✓' : i + 1}</span>
      <div><b>${esc(s.title)}</b><small>${esc(s.hint)}</small></div>
      ${i === next ? `<button class="btn small" type="button" onclick="go('${s.page}')">${esc(s.cta)}</button>` : ''}</li>`).join('');
    return `<section class="card welcome" aria-label="Primeros pasos"><header><h3>Empieza por aquí</h3>
      <button class="icon-btn" type="button" aria-label="Ocultar la guía" onclick="dppWelcomeHide()">×</button></header><ol>${items}</ol></section>`;
  }

  window.dppWelcomeHide = () => { try { localStorage.setItem(KEY, '1'); } catch (e) { /* private mode */ } render(); };
  window.DPPWelcome = {html};
})();
