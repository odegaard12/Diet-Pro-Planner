/*
 * Diet Pro Planner · home ("Resumen"), v0.3.0 layout chosen by the user:
 * week strip → big daily balance → four tiles with mini charts → "Tu día" timeline
 * ending with the Coach (dashboard-coach-v17.js fills #coachSlot) → AI coach.
 */
(function () {
  'use strict';

  let renderToken = 0;
  const DAY = 86400000;

  async function json(path) {
    const r = await fetch(path, {credentials: 'same-origin', cache: 'no-store'});
    if (r.status === 401) { location.reload(); throw new Error('Sesión caducada'); }
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  }

  const isoAdd = (iso, n) => localIso(new Date(new Date(iso + 'T12:00:00').getTime() + n * DAY));
  const sum = (arr, key) => arr.reduce((a, x) => a + Number(x[key] || 0), 0);
  const kcalOf = (d) => byDate(state.meals, d).reduce((a, m) => a + Number(m.totals?.kcal || 0), 0);
  const protOf = (d) => byDate(state.meals, d).reduce((a, m) => a + Number(m.totals?.protein || 0), 0);
  const sportOf = (d) => sum(byDate(state.workouts, d), 'kcal');
  function targets() {
    const c = window.DPP_PROFILE?.computed || {};
    return {kcal: Number(c.kcal_base_target || 0), protein: Number(c.protein?.target_g || 0)};
  }

  /* ---------- week strip ---------- */
  function weekStrip(d) {
    const t = targets();
    const dow = (new Date(d + 'T12:00:00').getDay() + 6) % 7;
    const monday = isoAdd(d, -dow);
    const letters = ['L', 'M', 'X', 'J', 'V', 'S', 'D'];
    const days = letters.map((l, i) => {
      const iso = isoAdd(monday, i);
      const kcal = kcalOf(iso);
      const dot = !kcal ? '' : (!t.kcal || Math.abs(kcal - t.kcal) <= t.kcal * 0.12) ? 'ok' : 'off';
      const cls = [iso === d ? 'is-selected' : '', iso > today() ? 'is-future' : '', iso === today() ? 'is-today' : ''].join(' ');
      return `<button type="button" class="wk-day ${cls}" ${iso > today() ? 'disabled' : ''} onclick="setSelectedDate('${iso}');render()" aria-label="${esc(iso)}"><span>${l}</span><b>${Number(iso.slice(8))}</b><i class="wk-dot ${dot}"></i></button>`;
    }).join('');
    return `<div class="wk-strip"><button type="button" class="wk-nav" aria-label="Semana anterior" onclick="shiftDay(-7)">‹</button>${days}<button type="button" class="wk-nav" aria-label="Semana siguiente" onclick="shiftDay(7)" ${isoAdd(monday, 7) > today() ? 'disabled' : ''}>›</button></div>`;
  }

  function header(d, eaten, target) {
    const long = new Date(d + 'T12:00:00').toLocaleDateString('es-ES', {weekday: 'short', day: 'numeric', month: 'short'}).toUpperCase();
    let pill = '<span class="pill">Sin registros</span>';
    if (eaten && target) pill = eaten > target * 1.1 ? '<span class="pill bad">Te pasas</span>' : '<span class="pill good">En objetivo</span>';
    const pending = readQueue().length;
    if (pending) pill = `<span class="pill warn" title="Se enviarán al recuperar la conexión">${pending} sin enviar</span>` + pill;
    const raw = new Date(d + 'T12:00:00').toLocaleDateString('es-ES', {weekday: 'long', day: 'numeric', month: 'long'});
    const big = raw.charAt(0).toUpperCase() + raw.slice(1);
    return `<div class="day-head"><label class="day-pick"><small>${d === today() ? 'HOY' : esc(long)}</small><b class="cap">${esc(big)}</b><input id="dashDate" type="date" value="${esc(d)}" aria-label="Elegir día" onchange="setSelectedDate(this.value);render()"></label>${pill}${d === today() ? '' : '<button class="btn small" type="button" onclick="setSelectedDate(today());render()">Hoy</button>'}</div>`;
  }

  /* ---------- big balance ---------- */
  function balance(d, data) {
    const summary = data.summary || {}, a = data.analysis || {};
    const eaten = Number(summary.kcal || 0);
    const target = Math.round(Number.isFinite(Number(a.kcal_margin)) && a.kcal_margin !== null ? eaten + Number(a.kcal_margin) : targets().kcal);
    const sport = sportOf(d);
    const free = Math.max(0, Math.round(target - eaten));
    const meals = byDate(state.meals, d).slice().sort((x, y) => String(x.time).localeCompare(String(y.time)));
    const scale = Math.max(target, eaten) || 1;
    const segs = meals.map((m, i) => `<i style="width:${(Number(m.totals?.kcal || 0) / scale * 100).toFixed(1)}%" class="seg ${i % 2 ? 'b' : 'a'}"></i>`).join('');
    const legend = meals.map((m) => `<span>${esc(m.name)} ${fmt(m.totals?.kcal)}</span>`).join('') + (sport ? `<span class="accent">Entreno +${fmt(sport)}</span>` : '');
    return {eaten, target, html: `<section class="balance">
      <div class="balance-top"><span>Balance del día</span><span>objetivo ${fmt(target)}</span></div>
      <div class="balance-big"><b>${eaten > target ? '+' + fmt(eaten - target) : fmt(free)}</b><span>${eaten > target ? 'kcal de más' : 'kcal libres'}</span></div>
      <div class="balance-bar">${segs}${sport ? `<i class="seg sport" style="width:${Math.min(100, sport / scale * 100).toFixed(1)}%"></i>` : ''}</div>
      <div class="balance-legend">${legend || '<span>Aún no hay comidas este día</span>'}</div>
    </section>`};
  }

  /* ---------- tiles with mini charts ---------- */
  function bars(values, color, max, ref) {
    const W = 140, H = 30, n = values.length, bw = 14, gap = (W - n * bw) / Math.max(1, n - 1);
    const m = Math.max(max || 0, ...values, 1);
    const rects = values.map((v, i) => {
      const h = v ? Math.max(4, v / m * (H - 4)) : 4;
      return `<rect x="${(i * (bw + gap)).toFixed(1)}" y="${(H - h).toFixed(1)}" width="${bw}" height="${h.toFixed(1)}" rx="3" class="${v ? color : 'empty'}"/>`;
    }).join('');
    const line = ref ? `<line x1="0" x2="${W}" y1="${(H - ref / m * (H - 4)).toFixed(1)}" y2="${(H - ref / m * (H - 4)).toFixed(1)}" class="ref"/>` : '';
    return `<svg class="spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">${rects}${line}</svg>`;
  }
  function spark(values) {
    const W = 140, H = 30;
    if (values.length < 2) return '<svg class="spark" viewBox="0 0 140 30" aria-hidden="true"></svg>';
    const min = Math.min(...values), max = Math.max(...values), span = max - min || 1;
    const pts = values.map((v, i) => [i / (values.length - 1) * W, 4 + (max - v) / span * (H - 8)]);
    const last = pts[pts.length - 1];
    return `<svg class="spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true"><polyline points="${pts.map((p) => p.map((x) => x.toFixed(1)).join(',')).join(' ')}" class="line"/><circle cx="${last[0].toFixed(1)}" cy="${last[1].toFixed(1)}" r="3" class="dot"/></svg>`;
  }
  function tile(label, value, unit, chart, note, tone) {
    return `<article class="tile"><span>${esc(label)}</span><b>${esc(value)}<small> ${esc(unit)}</small></b>${chart}<small class="${tone || ''}">${esc(note)}</small></article>`;
  }
  function tiles(d) {
    const t = targets();
    const last7 = Array.from({length: 7}, (_, i) => isoAdd(d, i - 6));
    const prot = protOf(d);
    const protTile = tile('Proteína', fmt(prot), t.protein ? `/ ${fmt(t.protein)} g` : 'g', bars(last7.map(protOf), 'p', t.protein, t.protein),
      !prot ? 'aún sin proteína hoy' : prot >= t.protein ? 'objetivo cumplido' : `faltan ${fmt(t.protein - prot)} g`, prot >= t.protein && prot ? 'good' : 'warn');

    const official = state.weights.filter((w) => w.official).sort((a, b) => (a.date + a.time).localeCompare(b.date + b.time));
    const recent = official.slice(-12);
    const lw = official[official.length - 1];
    const age = lw ? Math.round((new Date(today() + 'T12:00:00') - new Date(lw.date + 'T12:00:00')) / DAY) : null;
    const delta = recent.length > 1 ? Number(recent[recent.length - 1].kg) - Number(recent[0].kg) : null;
    const weightTile = lw
      ? tile('Peso', fmt(lw.kg), 'kg', spark(recent.map((w) => Number(w.kg))), age > 7 ? `último hace ${age} días` : (delta === null ? 'sigue pesándote' : `${delta > 0 ? '+' : ''}${fmt(delta)} kg en ${recent.length} pesajes`), age > 7 ? 'warn' : (delta !== null && delta <= 0 ? 'good' : ''))
      : tile('Peso', '—', 'kg', spark([]), 'registra tu peso de la mañana', 'warn');

    const sportDays = last7.map(sportOf);
    const sessions = state.workouts.filter((w) => last7.includes(w.date)).length;
    const sportTile = tile('Deporte 7 días', fmt(sportDays.reduce((a, b) => a + b, 0)), 'kcal', bars(sportDays, 's'), `${sessions} ${sessions === 1 ? 'sesión' : 'sesiones'}`);

    let rateTile;
    const since = isoAdd(today(), -28);
    const window4 = official.filter((w) => w.date >= since);
    if (window4.length >= 3) {
      const days = Math.max(7, (new Date(window4[window4.length - 1].date) - new Date(window4[0].date)) / DAY);
      const rate = (Number(window4[window4.length - 1].kg) - Number(window4[0].kg)) / days * 7;
      const tone = rate <= -0.2 && rate >= -1 ? 'good' : rate < -1 ? 'warn' : 'bad';
      const pos = Math.max(4, Math.min(136, 70 - rate * 60));
      rateTile = tile('Ritmo', `${rate > 0 ? '+' : ''}${fmt(rate)}`, 'kg/sem', `<svg class="spark" viewBox="0 0 140 30" aria-hidden="true"><rect x="0" y="12" width="140" height="8" rx="4" class="track"/><rect x="82" y="12" width="48" height="8" rx="4" class="zone"/><circle cx="${pos.toFixed(1)}" cy="16" r="7" class="knob ${tone}"/></svg>`,
        tone === 'good' ? 'bajada correcta' : tone === 'warn' ? 'bajada muy rápida' : 'sin bajada', tone);
    } else {
      rateTile = tile('Ritmo', '—', 'kg/sem', '<svg class="spark" viewBox="0 0 140 30" aria-hidden="true"><rect x="0" y="12" width="140" height="8" rx="4" class="track"/></svg>', 'faltan pesajes recientes', 'warn');
    }
    return `<section class="tiles">${protTile}${weightTile}${sportTile}${rateTile}</section>`;
  }

  /* ---------- "Tu día" timeline ---------- */
  function timeline(d) {
    const items = [
      ...byDate(state.meals, d).map((m) => ({time: m.time, kind: 'meal', html: `<div class="tl-card"><div><b>${esc(m.name)}</b><small>${window.DPPDashboardMealCard.itemSummary(m.items)}</small></div><strong>${fmt(m.totals?.kcal)}</strong><span class="mini-actions"><button class="mini-repeat" title="Repetir hoy" aria-label="Repetir hoy" onclick="repeatMeal(${Number(m.id)}, this)">↻</button><button class="mini-delete" title="Borrar" aria-label="Borrar" onclick="deleteMeal(${Number(m.id)})">×</button></span></div>`})),
      ...byDate(state.workouts, d).map((w) => ({time: w.time, kind: 'sport', html: `<div class="tl-card sport"><div><b>${esc(w.name)} · ${fmt(w.minutes)} min</b><small>${esc(cleanWorkoutNote(w.notes) || 'Entreno')}</small></div><strong>+${fmt(w.kcal)}</strong><span class="mini-actions"><button class="mini-delete" title="Borrar" aria-label="Borrar" onclick="deleteWorkout(${Number(w.id)})">×</button></span></div>`})),
    ].sort((a, b) => String(a.time).localeCompare(String(b.time)));
    const rows = items.map((it) => `<div class="tl-row ${it.kind}"><time>${esc(it.time || '')}</time><i></i>${it.html}</div>`).join('');
    const empty = items.length ? '' : '<div class="tl-row"><time></time><i></i><div class="tl-card empty-card">Nada registrado este día. Usa <b>Comidas</b> para añadir lo que comes; los entrenos de Strava entran solos.</div></div>';
    return `<h2 class="sec-title">Tu día</h2><section class="timeline">${rows}${empty}
      <div class="tl-row next"><time>Ahora</time><i></i><section id="coachSlot" class="tl-card coach-card"><div class="coach-body"><span class="coach-kicker">COACH · SIGUIENTE COMIDA</span><p class="muted">Calculando…</p></div></section></div>
    </section>`;
  }

  /* Big balance number counts up once (skipped with reduced motion). */
  function countUp(el) {
    if (!el || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const text = el.textContent, sign = text.startsWith('+') ? '+' : '';
    const target = Number(text.replace(/[^\d,]/g, '').replace(',', '.'));
    if (!Number.isFinite(target) || target <= 0) return;
    const t0 = performance.now(), dur = 600;
    const step = (t) => {
      const k = Math.min(1, (t - t0) / dur), eased = 1 - Math.pow(1 - k, 3);
      el.textContent = sign + fmt(Math.round(target * eased));
      if (k < 1) requestAnimationFrame(step); else el.textContent = text;
    };
    requestAnimationFrame(step);
  }

  function homeHtml(d, data) {
    const bal = balance(d, data);
    return `${header(d, bal.eaten, bal.target)}${weekStrip(d)}${bal.html}${tiles(d)}${timeline(d)}<div id="aiCoachSlot"></div>`;
  }

  async function renderHome() {
    const token = ++renderToken;
    const d = day();
    $('#view').innerHTML = `${weekStrip(d)}<section class="balance loading-card">Cargando el resumen del día…</section>`;
    try {
      const [data] = await Promise.all([
        json(`/api/food-intel/day?date=${encodeURIComponent(d)}`),
        window.DPP_PROFILE ? null : window.DPP?.loadProfile?.(),
      ]);
      if (token !== renderToken || page !== 'home') return;
      $('#view').innerHTML = homeHtml(d, data);
      countUp(document.querySelector('.balance-big b'));
      window.DPPCoachV17?.load(d);
      window.DPPAICoach?.mountHome('#aiCoachSlot', d);
    } catch (e) {
      if (token !== renderToken) return;
      $('#view').innerHTML = `${weekStrip(d)}<section class="card note-box"><h3>No pude cargar el resumen</h3><p>${esc(e.message || 'Error')}</p><button class="btn" onclick="render()">Reintentar</button></section>`;
    }
  }

  window.renderHome = renderHome;
  document.addEventListener('dpp:profile', () => { if (page === 'home' && document.querySelector('.balance')) render(); });
})();
