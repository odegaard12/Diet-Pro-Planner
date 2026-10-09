/*
 * Diet Pro Planner · "Progreso": trend weight, real rate, adaptive TDEE,
 * adherence and patterns from GET /api/analytics/overview.
 */
(function () {
  'use strict';

  let range = 60;
  let data = null;
  try { range = Number(localStorage.getItem('dppProgressRange')) || 60; } catch (e) { /* private mode */ }

  const C = () => window.DPPCharts.COLORS;
  const nf = (v, d = 1) => (v === null || v === undefined) ? '—' : Number(v).toLocaleString('es-ES', {maximumFractionDigits: d});
  const signed = (v, d = 2) => (v === null || v === undefined) ? '—' : `${v > 0 ? '+' : ''}${nf(v, d)}`;
  const longDate = (iso) => iso ? new Date(`${iso}T12:00:00`).toLocaleDateString('es-ES', {day: 'numeric', month: 'short', year: 'numeric'}) : '—';

  function tile(label, value, sub, tone) {
    return `<article class="pg-tile ${tone || ''}"><span>${esc(label)}</span><b>${esc(value)}</b><small>${esc(sub || '')}</small></article>`;
  }

  function tiles(d) {
    const s = d.summary, t = d.adaptive_tdee || {};
    const rate = s.rate_kg_week;
    const rateTone = rate === null ? '' : rate < -1 ? 'warn' : rate <= -0.2 ? 'good' : rate > 0.15 ? 'bad' : '';
    return `<section class="pg-tiles">
      ${tile('Peso tendencia', s.trend_weight ? `${nf(s.trend_weight, 1)} kg` : '—', `objetivo ${nf(s.goal_weight, 1)} kg`)}
      ${tile('Ritmo real', rate === null ? '—' : `${signed(rate)} kg/sem`, 'últimas 4 semanas', rateTone)}
      ${tile('Objetivo alcanzado', s.eta ? longDate(s.eta) : '—', s.eta ? 'a ritmo actual' : 'sin ritmo de bajada suficiente')}
      ${tile('Gasto real (TDEE)', t.tdee ? `${nf(t.tdee, 0)} kcal` : 'calibrando', t.tdee ? `confianza ${t.confidence}` : `${t.logged_days || 0}/14 días · ${t.weigh_ins || 0}/6 pesajes`)}
      ${tile('Racha registro', `${s.streak_days} días`, s.logging_pct === null ? '' : `${s.logging_pct}% días completos`, s.streak_days >= 7 ? 'good' : '')}
    </section>`;
  }

  function insights(d) {
    if (!d.insights.length) return '';
    const icon = {good: '✅', warn: '⚠️', bad: '🚨', info: '💡'};
    return `<section class="pg-insights">${d.insights.map((i) => `<article class="pg-insight ${esc(i.tone)}"><span aria-hidden="true">${icon[i.tone] || '💡'}</span><div><b>${esc(i.title)}</b><p>${esc(i.text)}</p></div></article>`).join('')}</section>`;
  }

  function weeklyTable(d) {
    const rows = d.weekly.slice().reverse().map((w) => `<tr><td>${esc(window.DPPCharts.shortDate(w.week))}</td><td>${w.logged_days}/7</td><td>${nf(w.avg_kcal, 0)}</td><td>${nf(w.avg_protein, 0)}</td><td>${nf(w.workout_kcal, 0)}</td><td>${nf(w.avg_weight, 1)}</td><td>${nf(w.trend_end, 1)}</td></tr>`).join('');
    return `<div class="pg-table-wrap"><table class="pg-table"><thead><tr><th>Semana</th><th>Días</th><th>kcal/día</th><th>Prot. g</th><th>Deporte kcal</th><th>Peso medio</th><th>Tendencia</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  }

  function foodsTable(items, key, unit) {
    if (!items.length) return '<div class="empty">Sin datos.</div>';
    const max = Math.max(...items.map((i) => Number(i[key]) || 0)) || 1;
    return `<ul class="pg-rank">${items.map((i) => `<li><div><b>${esc(i.name)}</b><small>${i.times} veces · ${nf(i.grams, 0)} g</small></div><i><em style="width:${(Number(i[key]) || 0) / max * 100}%"></em></i><strong>${nf(i[key], 0)} ${unit}</strong></li>`).join('')}</ul>`;
  }

  function dailyTable(d) {
    const rows = d.series.slice().reverse().map((x) => `<tr><td>${esc(x.date)}</td><td>${x.meals ? nf(x.kcal, 0) : '—'}</td><td>${nf(x.kcal_target, 0)}</td><td>${x.meals ? nf(x.protein, 0) : '—'}</td><td>${nf(x.workout_kcal, 0)}</td><td>${nf(x.weight, 2)}</td><td>${nf(x.trend, 2)}</td></tr>`).join('');
    return `<details class="pg-details"><summary>Ver datos diarios (tabla)</summary><div class="pg-table-wrap"><table class="pg-table"><thead><tr><th>Fecha</th><th>kcal</th><th>Objetivo</th><th>Prot. g</th><th>Deporte</th><th>Peso</th><th>Tendencia</th></tr></thead><tbody>${rows}</tbody></table></div></details>`;
  }

  function drawCharts(d) {
    const charts = window.DPPCharts; const s = d.series;
    const dates = s.map((x) => x.date);
    const goal = d.summary.goal_weight;
    const weights = s.map((x) => x.weight).filter((v) => v !== null);
    const nearGoal = weights.length && goal >= Math.min(...weights) - 3;
    if (document.querySelector('#pgWeight')) charts.timeChart('#pgWeight', {
      dates, ariaLabel: 'Peso diario y tendencia', unit: ' kg',
      series: [
        {label: 'Pesaje', type: 'dots', color: C().muted, values: s.map((x) => x.weight), unit: ' kg', digits: 2},
        {label: 'Tendencia', type: 'line', color: C().s1, values: s.map((x) => x.trend), unit: ' kg', digits: 1, endLabel: true, width: 2.5},
      ],
      ref: nearGoal ? {value: goal, label: `Objetivo ${nf(goal, 1)} kg`} : null,
    });
    if (!document.querySelector('#pgEnergy')) return;
    charts.timeChart('#pgEnergy', {
      dates, zeroBased: true, ariaLabel: 'Calorías diarias frente al objetivo', tickDigits: 0,
      series: [
        {label: 'Ingesta', type: 'bar', color: C().s1, values: s.map((x) => (x.meals ? x.kcal : null)), unit: ' kcal', digits: 0},
        {label: 'Objetivo del día', type: 'step', color: C().ref, values: s.map((x) => x.kcal_target), unit: ' kcal', digits: 0, width: 1.5},
      ],
      extraTooltip: [{label: 'Deporte', color: C().s2, values: s.map((x) => x.workout_kcal), unit: ' kcal', digits: 0}],
    });
    const p = d.targets.protein;
    charts.timeChart('#pgProtein', {
      dates, zeroBased: true, ariaLabel: 'Proteína diaria', tickDigits: 0,
      series: [{label: 'Proteína', type: 'bar', color: C().s1, values: s.map((x) => (x.meals ? x.protein : null)), unit: ' g', digits: 0}],
      ref: {value: p.goal_min_g, label: `Mínimo objetivo ${p.goal_min_g} g`},
    });
    if (d.macro_split) {
      const m = d.macro_split;
      charts.stackBar('#pgMacros', [
        {label: 'Proteína', value: m.protein_pct, color: C().s1, display: `${nf(m.protein_g, 0)} g · ${m.protein_pct}%`},
        {label: 'Hidratos', value: m.carbs_pct, color: C().s2, display: `${nf(m.carbs_g, 0)} g · ${m.carbs_pct}%`},
        {label: 'Grasa', value: m.fat_pct, color: C().s3, display: `${nf(m.fat_g, 0)} g · ${m.fat_pct}%`},
      ]);
    }
  }

  function view(d) {
    const s = d.summary;
    const ranges = [30, 60, 90, 180].map((n) => `<button class="${n === range ? 'is-active' : ''}" onclick="dppProgressRange(${n})">${n} días</button>`).join('');
    const hasWeights = d.series.some((x) => x.weight !== null);
    const hasDays = s.complete_days > 0;
    const nutrition = hasDays ? `
        <article class="card pg-card"><header><h3>Energía diaria</h3><p class="muted">Media ${nf(s.avg_kcal, 0)} kcal en días completos · dentro de ±10%: ${s.kcal_in_range_days}/${s.complete_days}</p></header><div id="pgEnergy"></div></article>
        <article class="card pg-card"><header><h3>Proteína diaria</h3><p class="muted">Media ${nf(s.avg_protein, 0)} g · en objetivo ${s.protein_hit_days}/${s.complete_days} días</p></header><div id="pgProtein"></div></article>
        <article class="card pg-card"><header><h3>Reparto de macros</h3><p class="muted">Media de días completos (% de kcal)</p></header><div id="pgMacros"></div></article>
        <article class="card pg-card"><header><h3>Lo que más calorías aporta</h3></header>${foodsTable(d.top_foods_kcal, 'kcal', 'kcal')}</article>
        <article class="card pg-card"><header><h3>Tus fuentes de proteína</h3></header>${foodsTable(d.top_foods_protein, 'protein', 'g')}</article>`
      : `<article class="card pg-card pg-wide"><header><h3>Comida y proteína</h3></header><div class="empty">Aún no hay días completos en este rango. Registra todas las comidas de un día para ver energía, proteína y macros.<div class="empty-cta"><button class="btn small" onclick="go('register')">Registrar comida</button></div></div></article>`;
    return `<section class="pg-head"><p class="muted">${esc(window.DPPCharts.shortDate(d.range.from))} – ${esc(window.DPPCharts.shortDate(d.range.to))}</p><div class="pg-range" role="group" aria-label="Rango">${ranges}</div></section>
      ${tiles(d)}
      ${insights(d)}
      <section class="pg-grid">
        <article class="card pg-card pg-wide"><header><h3>Peso y tendencia</h3><p class="muted">Puntos = pesajes oficiales · línea = tendencia</p></header>${hasWeights ? '<div id="pgWeight"></div>' : '<div class="empty">No hay pesos en este rango.<div class="empty-cta"><button class="btn small" onclick="go(\'weights\')">Registrar peso</button></div></div>'}</article>
        ${nutrition}
        <article class="card pg-card pg-wide"><header><h3>Deporte</h3></header><div class="pg-mini"><span><b>${nf(s.workout_sessions, 0)}</b><small>sesiones</small></span><span><b>${nf(s.workout_kcal, 0)}</b><small>kcal deporte</small></span><span><b>${nf(s.weekday_avg_kcal, 0)}</b><small>kcal/día entre semana</small></span><span><b>${nf(s.weekend_avg_kcal, 0)}</b><small>kcal/día fin de semana</small></span></div></article>
        <article class="card pg-card pg-wide"><header><h3>Resumen semanal</h3></header>${weeklyTable(d)}</article>
      </section>
      ${dailyTable(d)}
      <div class="footer-space"></div>`;
  }

  async function renderProgress() {
    $('#view').innerHTML = '<section class="card"><h3>Calculando progreso…</h3><p class="muted">Tendencia, ritmo, gasto real y adherencia.</p></section>';
    try {
      data = await api(`/api/analytics/overview?days=${range}`);
      if (page !== 'progress') return;
      $('#view').innerHTML = view(data);
      drawCharts(data);
    } catch (e) {
      $('#view').innerHTML = `<section class="card note-box"><h3>No pude calcular el progreso</h3><p>${esc(e.message)}</p><button class="btn" onclick="render()">Reintentar</button></section>`;
    }
  }

  window.dppProgressRange = (n) => { range = n; try { localStorage.setItem('dppProgressRange', String(n)); } catch (e) { /* ignore */ } renderProgress(); };
  window.DPP.registerPage({id: 'progress', icon: '📈', label: 'Progreso', sub: 'Tendencias', title: 'Progreso', after: 'home', render: renderProgress});
})();
