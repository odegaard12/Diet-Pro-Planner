/*
 * Diet Pro Planner · home ("Resumen") powered by Food Intelligence.
 * Smart Coach (dashboard-coach-v17.js) and the AI coach enrich it after render.
 */
(function () {
  'use strict';

  let renderToken = 0;

  async function json(path) {
    const r = await fetch(path, {credentials: 'same-origin', cache: 'no-store'});
    if (r.status === 401) { location.reload(); throw new Error('Sesión caducada'); }
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  }

  function weightBlock() {
    const lw = latestWeight();
    const profile = window.DPP_PROFILE?.profile || {};
    const goal = Number(profile.goal_weight_kg || 80);
    const start = Number(profile.start_weight_kg || (lw ? lw.kg : goal));
    if (!lw) return `<section class="fi13-weight"><div><span>Peso hacia ${fmt(goal)} kg</span><b>Sin dato</b><small>Registra peso oficial</small></div></section>`;
    const current = Number(lw.kg);
    const lost = Math.max(0, start - current), remaining = Math.max(0, current - goal);
    const pct = Math.max(0, Math.min(100, lost / Math.max(0.1, start - goal) * 100));
    return `<section class="fi13-weight">
      <div class="fi13-weight-main"><span>Peso hacia ${fmt(goal)} kg</span><b>${current.toLocaleString('es-ES', {maximumFractionDigits: 2})} kg</b><small>${esc(lw.date || '')} · ${lw.official ? 'oficial' : 'referencia'}</small></div>
      <div class="fi13-weight-progress"><i><em style="width:${pct}%"></em></i><div>
        <span><b>${fmt(lost)}</b><small>kg perdidos</small></span><span><b>${fmt(remaining)}</b><small>kg restantes</small></span><span><b>${fmt(goal)}</b><small>objetivo</small></span>
      </div></div></section>`;
  }

  function bodySnapshot(data) {
    if (!data || !data.available) return '';
    const m = data.metrics || {}, d = data.derived || {};
    const v = (k) => (m[k] || {}).value;
    const f = (x, dec = 1) => (x === null || x === undefined || x === '') ? '--' : Number(x).toLocaleString('es-ES', {maximumFractionDigits: dec});
    const bio = v('biocharge_wakeup') ?? v('biocharge_current') ?? v('biocharge');
    return `<section id="dppBodySnapshotCard" class="bs14-card bs14-compact">
      <div class="bs14-topline"><div><span>Foto corporal</span><h3>Composición corporal</h3><p>${esc(data.date || '')} ${data.time ? '· ' + esc(data.time) : ''} · lectura opcional de báscula</p></div>
        <div class="bs14-status-pill"><b>${f(bio, 0)}</b><small>BioCharge</small></div></div>
      <div class="bs14-compact-body">
        <div class="bs14-mini-person"><div class="bs14-person"><i class="head"></i><i class="torso"></i><i class="legs"></i></div>
          <div><b>${f(v('body_fat_pct'))}% grasa</b><small>${f(v('water_pct'))}% agua · ${f(v('muscle_mass_kg'))} kg músculo · ${d.fat_mass_kg ? f(d.fat_mass_kg) + ' kg grasa' : 'bioimpedancia'}</small></div></div>
        <div class="bs14-compact-grid"><article class="watch"><span>Grasa</span><b>${f(v('body_fat_pct'))}%</b></article><article><span>Agua</span><b>${f(v('water_pct'))}%</b></article><article><span>Músculo</span><b>${f(v('muscle_mass_kg'))} kg</b></article><article class="watch"><span>Visceral</span><b>${f(v('visceral_fat'), 0)}</b></article></div>
      </div>
      <p class="bs14-note">Dato estimado por bioimpedancia. Úsalo como tendencia semanal, no para juzgar un peso aislado. <a href="/weight-2">Ver Peso 2.0</a></p>
    </section>`;
  }

  function metric(label, value, sub, tone) {
    return `<article class="fi13-metric ${tone || 'ok'}"><span>${esc(label)}</span><b>${esc(value)}</b><small>${esc(sub || '')}</small></article>`;
  }

  function lists(d) {
    const meals = byDate(state.meals, d), workouts = byDate(state.workouts, d);
    const mt = mealTotals(meals), sport = workoutTotals(workouts);
    return `<section class="fi13-lower-grid">
      <article class="card fi13-panel"><header><div><h3>Comidas registradas</h3><p>${fmt(mt.kcal)} kcal · ${fmt(mt.protein)} g proteína</p></div><button class="btn small" onclick="go('register')">+ Comida</button></header>
        <div class="compact-list">${meals.length ? meals.map(mealCardCompact).join('') : '<div class="empty">Sin comidas.</div>'}</div></article>
      <article class="card fi13-panel"><header><div><h3>Actividad</h3><p>${fmt(sport)} kcal</p></div><button class="btn small" onclick="go('sport')">+ Entreno</button></header>
        <div class="compact-list">${workouts.length ? workouts.map(workoutCardCompact).join('') : '<div class="empty">Sin entrenos para este día.</div>'}</div></article>
    </section>`;
  }

  function homeHtml(d, data, snapshot) {
    const a = data.analysis || {}, rules = a.rules || {}, summary = data.summary || {}, conf = data.confidence || {};
    const protein = rules.protein || {}, energy = rules.energy || {}, oil = rules.oil || {}, activity = rules.training_alignment || {}, salt = rules.salt || {};
    const recs = (a.recommendations || []).slice(0, 3);
    return `${dateBar()}
      <section class="fi13-hero ${esc(a.semaphore || 'green')}">
        <div><span class="fi13-kicker">Inteligencia del día</span><h2>${esc(a.label || 'Análisis')}</h2><p>${esc(a.main_action || 'Analizando día.')}</p>
          <div class="fi13-hero-tags"><span>Confianza ${esc(conf.label || 'media')}</span><span>${esc((conf.reasons || []).slice(0, 1).join(' · ') || 'datos locales')}</span></div></div>
        <div class="fi13-score"><b>${a.score == null ? '--' : esc(a.score)}</b><small>score</small></div>
      </section>
      ${weightBlock()}
      ${snapshot}
      <section class="fi13-metrics">
        ${metric('Proteína', `${fmt(summary.protein)} g`, protein.message || 'objetivo diario', protein.status === 'ok' ? 'ok' : 'watch')}
        ${metric('Energía', `${fmt(a.kcal_margin)} kcal`, 'margen vs objetivo', energy.status === 'ok' ? 'ok' : 'watch')}
        ${metric('Aceite', `${fmt(summary.oil_g)} g`, oil.message || 'aceite medido', oil.status === 'ok' ? 'ok' : 'watch')}
        ${metric('Entreno', `${fmt((data.workouts || {}).kcal)} kcal`, activity.message || 'sin entreno', activity.status === 'ok' ? 'ok' : 'watch')}
      </section>
      <div id="aiCoachSlot"></div>
      <section class="fi13-main-grid">
        <article class="card fi13-panel fi13-next"><header><div><h3>Qué hacer ahora</h3><p>${byDate(state.meals, d).length} comidas · ${byDate(state.workouts, d).length} entrenos · sal ${salt.status === 'watch' ? 'a vigilar' : 'ok'}</p></div><button id="fi13SuggestBtn" class="btn small">Actualizar</button></header>
          <ul>${recs.length ? recs.map((x) => `<li>${esc(x)}</li>`).join('') : '<li>Sin alertas relevantes.</li>'}</ul><div id="fi13Suggestions" class="fi13-suggestions"></div></article>
        <article class="card fi13-panel"><header><div><h3>Peso oficial</h3><p>Lecturas recientes · <a href="#" onclick="go('progress');return false">ver progreso</a></p></div></header>${weightChart()}</article>
      </section>
      ${lists(d)}
      <div class="footer-space"></div>`;
  }

  async function renderHome() {
    const token = ++renderToken;
    const d = day();
    document.body.classList.add('fi13-home');
    $('#view').innerHTML = `${dateBar()}<section class="card fi13-loading"><h3>Cargando inteligencia del día…</h3><p class="muted">Calculando comida, peso, deporte, confianza y recomendaciones.</p></section>`;
    try {
      const [data, snap] = await Promise.all([
        json(`/api/food-intel/day?date=${encodeURIComponent(d)}`),
        json('/api/body-snapshot/latest').catch(() => null),
      ]);
      if (token !== renderToken || page !== 'home') return;
      $('#view').innerHTML = homeHtml(d, data, bodySnapshot(snap));
      window.DPPCoachV17?.load();
      window.DPPAICoach?.mountHome('#aiCoachSlot', d);
    } catch (e) {
      if (token !== renderToken) return;
      $('#view').innerHTML = `${dateBar()}<section class="card note-box"><h3>No pude cargar el resumen</h3><p>${esc(e.message || 'Error')}</p><button class="btn" onclick="render()">Reintentar</button></section>`;
    }
  }

  window.renderHome = renderHome;
  document.addEventListener('dpp:profile', () => { if (page === 'home' && document.querySelector('.fi13-weight')) document.querySelector('.fi13-weight').outerHTML = weightBlock(); });
})();
