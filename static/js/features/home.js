/*
 * Diet Pro Planner · home ("Resumen").
 * Layout: today KPIs → Coach (dashboard-coach-v17.js fills #coachSlot) → AI coach →
 * meals | activity → weight | body composition. Empty states say what to do next.
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

  const pct = (value, target) => (target > 0 ? Math.max(0, Math.min(100, value / target * 100)) : 0);
  const daysSince = (iso) => Math.round((new Date(today() + 'T12:00:00') - new Date(iso + 'T12:00:00')) / 86400000);

  function kpi(label, value, unit, sub, progress, tone) {
    const bar = progress === null ? '' : `<span class="bar" role="presentation"><i style="width:${progress.toFixed(0)}%"></i></span>`;
    return `<article class="kpi ${tone || ''}"><span>${esc(label)}</span><b>${esc(value)}${unit ? ` <small>${esc(unit)}</small>` : ''}</b>${bar}<small>${esc(sub)}</small></article>`;
  }

  function kpis(data) {
    const summary = data.summary || {}, a = data.analysis || {};
    const computed = window.DPP_PROFILE?.computed || {};
    const eaten = Number(summary.kcal || 0), protein = Number(summary.protein || 0);
    const kcalTarget = Number.isFinite(Number(a.kcal_margin)) && a.kcal_margin !== null ? eaten + Number(a.kcal_margin) : Number(computed.kcal_base_target || 0);
    const protTarget = Number(computed.protein?.target_g || 0);
    const sport = {kcal: (data.workouts || {}).kcal || 0, count: byDate(state.workouts, day()).length};
    const kcalTone = !eaten ? 'empty-kpi' : eaten > kcalTarget * 1.1 ? 'bad' : 'good';
    const protTone = !protein ? 'empty-kpi' : protein >= protTarget * 0.95 ? 'good' : 'warn';
    const lw = latestWeight();
    const goal = Number(window.DPP_PROFILE?.profile?.goal_weight_kg || 0);
    let weight;
    if (!lw) weight = kpi('Peso', '—', '', 'Registra tu peso de la mañana', null, 'empty-kpi');
    else {
      const age = daysSince(lw.date);
      const when = age <= 0 ? 'hoy' : age === 1 ? 'ayer' : `hace ${age} días`;
      const rest = goal ? Math.max(0, Number(lw.kg) - goal) : 0;
      weight = kpi('Peso', fmt(lw.kg), 'kg', `${when}${goal ? ` · faltan ${fmt(rest)} kg` : ''}`, null, age > 7 ? 'warn' : '');
    }
    return `<section class="home-kpis">
      ${kpi('Calorías', fmt(eaten), kcalTarget ? `/ ${fmt(kcalTarget)} kcal` : 'kcal', eaten ? `${fmt(Math.max(0, kcalTarget - eaten))} kcal disponibles` : 'Aún no has registrado comida', kcalTarget ? pct(eaten, kcalTarget) : null, kcalTone)}
      ${kpi('Proteína', fmt(protein), protTarget ? `/ ${fmt(protTarget)} g` : 'g', protein ? `${fmt(Math.max(0, protTarget - protein))} g para el objetivo` : 'Prioridad del día', protTarget ? pct(protein, protTarget) : null, protTone)}
      ${kpi('Entreno', fmt(sport.kcal || 0), 'kcal', sport.count ? `${sport.count} actividad${sport.count > 1 ? 'es' : ''}` : 'Sin entreno hoy', null, sport.kcal ? 'good' : 'empty-kpi')}
      ${weight}
    </section>`;
  }

  function coach(data) {
    const a = data.analysis || {};
    const recs = (a.recommendations || []).slice(0, 3);
    const tone = {green: 'good', yellow: 'warn', red: 'bad'}[a.semaphore] || 'info';
    return `<section id="coachSlot" class="card coach-card">
      <header><div><h3>Coach del día <span class="pill ${tone}">${esc(a.label || 'Análisis')}${a.score == null ? '' : ` · ${esc(a.score)}`}</span></h3><p>${esc(a.main_action || '')}</p></div>
        <button class="btn small secondary" data-coach-refresh type="button">Actualizar</button></header>
      <div class="coach-body"><ul class="coach-list">${recs.length ? recs.map((x) => `<li>${esc(x)}</li>`).join('') : '<li>Sin alertas relevantes.</li>'}</ul></div>
    </section>`;
  }

  function lists(d) {
    const meals = byDate(state.meals, d), workouts = byDate(state.workouts, d);
    const mt = mealTotals(meals), sport = workoutTotals(workouts);
    return `<section class="home-two">
      <article class="card"><header><div><h3>Comidas</h3><p>${meals.length ? `${fmt(mt.kcal)} kcal · ${fmt(mt.protein)} g proteína` : 'Nada registrado este día'}</p></div><button class="btn small" onclick="go('register')">+ Comida</button></header>
        <div class="compact-list">${meals.length ? meals.map(mealCardCompact).join('') : '<div class="empty">Registra la primera comida del día: busca alimentos o carga una plantilla.</div>'}</div></article>
      <article class="card"><header><div><h3>Actividad</h3><p>${workouts.length ? `${fmt(sport)} kcal` : 'Sin entrenos este día'}</p></div><button class="btn small secondary" onclick="go('sport')">+ Entreno</button></header>
        <div class="compact-list">${workouts.length ? workouts.map(workoutCardCompact).join('') : '<div class="empty">Strava importa tus actividades solo; también puedes añadirlas a mano.</div>'}</div></article>
    </section>`;
  }

  function bodySnapshot(data) {
    if (!data || !data.available) return '';
    const m = data.metrics || {};
    const v = (k) => (m[k] || {}).value;
    const keys = ['body_fat_pct', 'water_pct', 'muscle_mass_kg', 'visceral_fat'];
    if (keys.every((k) => v(k) === null || v(k) === undefined || v(k) === '')) return '';
    const f = (x, dec = 1) => (x === null || x === undefined || x === '') ? '—' : Number(x).toLocaleString('es-ES', {maximumFractionDigits: dec});
    const bio = v('biocharge_wakeup') ?? v('biocharge_current') ?? v('biocharge');
    return `<article id="dppBodySnapshotCard" class="card bs14-card">
      <div class="bs14-topline"><div><span>Composición corporal</span><h3>${esc(data.date || '')}</h3><p>Bioimpedancia: úsala como tendencia semanal.</p></div>
        ${bio == null ? '' : `<div class="bs14-status-pill"><b>${f(bio, 0)}</b><small>BioCharge</small></div>`}</div>
      <div class="bs14-compact-grid"><article><span>Grasa</span><b>${f(v('body_fat_pct'))}%</b></article><article><span>Agua</span><b>${f(v('water_pct'))}%</b></article><article><span>Músculo</span><b>${f(v('muscle_mass_kg'))} kg</b></article><article><span>Visceral</span><b>${f(v('visceral_fat'), 0)}</b></article></div>
      <p class="bs14-note"><a href="/weight-2">Ver Peso 2.0</a></p>
    </article>`;
  }

  function homeHtml(d, data, snapshot) {
    return `${dateBar()}
      ${kpis(data)}
      ${coach(data)}
      <div id="aiCoachSlot"></div>
      ${lists(d)}
      <section class="home-two">
        <article class="card"><header><div><h3>Peso</h3><p>Pesos oficiales recientes · <a href="#" onclick="go('progress');return false">ver progreso</a></p></div><button class="btn small secondary" onclick="go('weights')">+ Peso</button></header>${weightChart()}</article>
        ${snapshot || ''}
      </section>`;
  }

  async function renderHome() {
    const token = ++renderToken;
    const d = day();
    $('#view').innerHTML = `${dateBar()}<section class="card loading-card">Cargando el resumen del día…</section>`;
    try {
      const [data, snap] = await Promise.all([
        json(`/api/food-intel/day?date=${encodeURIComponent(d)}`),
        json('/api/body-snapshot/latest').catch(() => null),
        window.DPP_PROFILE ? null : window.DPP?.loadProfile?.(),
      ]);
      if (token !== renderToken || page !== 'home') return;
      $('#view').innerHTML = homeHtml(d, data, bodySnapshot(snap));
      window.DPPCoachV17?.load(d);
      window.DPPAICoach?.mountHome('#aiCoachSlot', d);
    } catch (e) {
      if (token !== renderToken) return;
      $('#view').innerHTML = `${dateBar()}<section class="card note-box"><h3>No pude cargar el resumen</h3><p>${esc(e.message || 'Error')}</p><button class="btn" onclick="render()">Reintentar</button></section>`;
    }
  }

  window.renderHome = renderHome;
  document.addEventListener('dpp:profile', () => { if (page === 'home' && document.querySelector('.home-kpis')) render(); });
})();
