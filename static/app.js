/*
 * Diet Pro Planner · core UI (classic script; other modules rely on its globals).
 *
 * v0.1.0 cleanup: this file used to stack several generations of overrides
 * (4x renderHome, 3x renderIntegrations/renderPlan, a fetch() monkeypatch and
 * DOM polling every 1-3 s). Only the live code remains, with user data escaped.
 * New features live in static/js/features/*.js, not here.
 */

let state = null; let page = 'home'; let mealItems = []; let selectedFoodPhoto = '';
let selectedDate = (() => { try { return localStorage.getItem('selectedDate') || ''; } catch (e) { return ''; } })();
let __stravaPreview = []; // shared with strava-v018.js

const PAGES = [['home', '🏠', 'Resumen'], ['register', '⚡', 'Registrar'], ['sport', '🏋️', 'Deporte'], ['templates', '🍽️', 'Plantillas'], ['foods', '🥫', 'Alimentos'], ['plan', '📅', 'Plan'], ['weights', '⚖️', 'Historial peso'], ['integrations', '🔗', 'Integraciones'], ['history', '📚', 'Historial']];
const UI5_NAV = {home: ['🏠', 'Resumen', 'Panel diario'], register: ['🍽️', 'Registrar', 'Comidas'], sport: ['🏋️', 'Deporte', 'Strava/manual'], templates: ['⚡', 'Plantillas', '2 clics'], foods: ['🥫', 'Alimentos', 'Productos/OCR'], plan: ['📅', 'Plan', 'Semana'], weights: ['⚖️', 'Peso', 'Historial'], integrations: ['🔗', 'Integraciones', 'Strava'], history: ['📚', 'Historial', 'Todo']};
const PAGE_TITLES = {home: 'Resumen', register: 'Registrar / comida', templates: 'Plantillas rápidas', foods: 'Alimentos comprados', sport: 'Registrar deporte', plan: 'Plan semanal', weights: 'Historial de peso', integrations: 'Integraciones', history: 'Historial completo'};

const $ = (s) => document.querySelector(s);
const fmt = (n) => Number(n || 0).toLocaleString('es-ES', {maximumFractionDigits: 1});
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const ui5Esc = esc;
const localIso = (d = new Date()) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
// Device clock, not the time of the last page load (a tab left open overnight logged onto yesterday).
const today = () => localIso();
const nowHM = () => new Date().toTimeString().slice(0, 5);
const day = () => selectedDate || today();
function remember(key, value) { try { localStorage.setItem(key, value); } catch (e) { /* private mode */ } }
function setSelectedDate(value) { selectedDate = value; remember('selectedDate', value); }

let toastLockUntil = 0; // keeps "guardado en el móvil" visible over the caller's own "guardado" toast
function toast(msg, lock) { if (!lock && Date.now() < toastLockUntil) return; if (lock) toastLockUntil = Date.now() + 2500; const t = $('#toast'); if (!t) return; t.textContent = msg; t.classList.add('show'); clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove('show'), 2600); }
/* Offline queue: new meals, weights and workouts saved without connection wait on this device
   (localStorage) and are sent in order as soon as the Raspberry is reachable again. */
const QUEUE_KEY = 'dppQueue', QUEUEABLE = ['/api/meals', '/api/weights', '/api/workouts'];
function readQueue() { try { return JSON.parse(localStorage.getItem(QUEUE_KEY) || '[]'); } catch (e) { return []; } }
function writeQueue(q) { try { localStorage.setItem(QUEUE_KEY, JSON.stringify(q)); } catch (e) { /* private mode */ } }
let flushing = false;
async function flushQueue() {
  const q = readQueue();
  if (flushing || !q.length || !navigator.onLine) return;
  flushing = true;
  let sent = 0;
  try {
    while (q.length) {
      const job = q[0];
      let r;
      try { r = await fetch(job.path, {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json'}, body: job.body}); } catch (e) { break; }
      if (r.status === 401 || r.status >= 500) break; // keep it: sign in again / server busy
      q.shift(); writeQueue(q); // 2xx sent; 4xx would never succeed, drop it
      if (r.ok) sent += 1;
    }
  } finally { flushing = false; }
  if (sent) { toast(`${sent} registro${sent > 1 ? 's' : ''} guardado${sent > 1 ? 's' : ''} sin conexión ya enviado${sent > 1 ? 's' : ''}`); load().catch(() => {}); }
}
async function api(path, opts = {}) {
  if ((opts.method || 'GET') === 'POST' && QUEUEABLE.includes(path)) {
    try {
      const r = await fetch(path, {credentials: 'same-origin', headers: {'Content-Type': 'application/json'}, ...opts});
      if (r.status === 503 && !navigator.onLine) throw new TypeError('offline');
      return handle(r);
    } catch (e) {
      if (!(e instanceof TypeError)) throw e; // a real API error, not a network failure
      const q = readQueue(); q.push({path, body: opts.body, at: Date.now()}); writeQueue(q);
      toast('Sin conexión: guardado en el móvil, se enviará al volver', true);
      return {ok: true, queued: true};
    }
  }
  return handle(await fetch(path, {credentials: 'same-origin', headers: {'Content-Type': 'application/json'}, ...opts}));
}
async function handle(r) {
  if (r.status === 401) { location.reload(); throw new Error('Sesión caducada'); }
  if (!r.ok) { let e = `Error ${r.status}`; try { e = (await r.json()).error || e; } catch (x) { /* not JSON */ } throw new Error(e); }
  return r.json();
}
async function apiForm(path, form) {
  const r = await fetch(path, {method: 'POST', body: form, credentials: 'same-origin'});
  if (!r.ok) { let e = `Error ${r.status}`; try { e = (await r.json()).error || e; } catch (x) { /* not JSON */ } throw new Error(e); }
  return r.json();
}
/* Disable the clicked button while an async action runs (prevents double saves). */
async function busy(btn, fn) {
  if (btn?.disabled) return;
  if (btn) btn.disabled = true;
  try { return await fn(); } catch (e) { toast(e.message || 'Error'); } finally { if (btn) btn.disabled = false; }
}

async function load() { state = await api('/api/state'); if (!selectedDate) setSelectedDate(today()); renderNav(); render(); }
function renderNav() {
  const nav = $('#nav'); if (!nav) return;
  nav.innerHTML = PAGES.map(([id, ico, label]) => { const p = UI5_NAV[id] || [ico, label, '']; return `<button class="${page === id ? 'active' : ''}" data-page="${id}"><span class="nav-ico">${p[0]}</span><span class="nav-copy"><b>${esc(p[1])}</b><small>${esc(p[2])}</small></span></button>`; }).join('');
  nav.querySelectorAll('[data-page]').forEach((b) => { b.onclick = () => go(b.dataset.page); });
}
function setTitle(t) { const el = $('#pageTitle'); if (el) el.textContent = t; }
function go(p) { page = p; document.body.classList.toggle('fi13-home', p === 'home'); renderNav(); render(); document.dispatchEvent(new CustomEvent('dpp:page', {detail: p})); try { window.scrollTo({top: 0}); } catch (e) { /* old browsers */ } }
function render() {
  setTitle(PAGE_TITLES[page] || (window.DPP_PAGE_TITLES || {})[page] || 'Diet Pro Planner');
  const name = {home: 'renderHome', register: 'renderRegister', templates: 'renderTemplates', foods: 'renderFoods', sport: 'renderSport', plan: 'renderPlan', weights: 'renderWeights', integrations: 'renderIntegrations', history: 'renderHistory'}[page];
  if (typeof window[name] === 'function') window[name]();
  document.body.classList.toggle('fi13-home', page === 'home');
  setTimeout(ui5ApplyShell, 0);
}

function byDate(arr, d = day()) { return (arr || []).filter((x) => x.date === d); }
function mealTotals(meals) { return meals.reduce((a, m) => { a.kcal += (m.totals?.kcal || 0); a.protein += (m.totals?.protein || 0); a.oil += (m.items || []).filter((i) => /aceite/i.test(i.food_name)).reduce((x, i) => x + Number(i.grams || 0), 0); return a; }, {kcal: 0, protein: 0, oil: 0}); }
function workoutTotals(ws) { return ws.reduce((a, w) => a + Number(w.kcal || 0), 0); }
function latestWeight() { return [...state.weights].sort((a, b) => (b.date + b.time).localeCompare(a.date + a.time))[0]; }
function foodByName(n) { return state.foods.find((f) => f.name === n); }
function foodById(id) { return state.foods.find((f) => Number(f.id) === Number(id)); }
function calcFood(f, g) { const k = Number(g || 0) / 100; return {food_id: f.id, food_name: f.name, grams: Number(g || 0), kcal: f.kcal * k, protein: f.protein * k, carbs: f.carbs * k, fat: f.fat * k, sugar: f.sugar * k, salt: f.salt * k}; }
function calcList(items) { return items.reduce((a, i) => { a.kcal += Number(i.kcal || 0); a.protein += Number(i.protein || 0); a.fat += Number(i.fat || 0); a.carbs += Number(i.carbs || 0); a.oil += /aceite/i.test(i.food_name) ? Number(i.grams || 0) : 0; return a; }, {kcal: 0, protein: 0, fat: 0, carbs: 0, oil: 0}); }
function mealAdvice(items) {
  const t = calcList(items); let cls = 'good', label = 'BIEN', text = 'Buen plato para bajar peso y mantener fuerza.';
  if (t.kcal < 250) { cls = 'warn'; label = 'POCO'; text = 'Puede quedarse corto: añade proteína o fruta si toca entrenar.'; }
  if (t.protein < 20) { cls = 'warn'; label = 'MÁS PROTEÍNA'; text = 'Sube pollo, huevos, atún, yogur o queso fresco.'; }
  if (t.kcal > 850) { cls = 'bad'; label = 'ALTO'; text = 'Ración alta: reduce carbohidrato, pan o cantidad total.'; }
  if (t.oil > 10) { cls = 'bad'; label = 'ACEITE ALTO'; text = 'Aceite alto: 5 g normal, 10 g máximo.'; }
  if (t.kcal >= 350 && t.kcal <= 750 && t.protein >= 25 && t.oil <= 10) { cls = 'good'; label = 'BIEN'; text = 'Buen plato: saciante, proteína decente y aceite controlado.'; }
  return {cls, label, text, t};
}

function shiftDay(n) { const d = new Date(day() + 'T12:00:00'); d.setDate(d.getDate() + n); setSelectedDate(localIso(d)); render(); }
/* Compact day switcher: ‹ day › ; the transparent date input over the label opens the native picker. */
function dateBar() {
  const d = day(), isToday = d === today();
  const long = new Date(d + 'T12:00:00').toLocaleDateString('es-ES', {weekday: 'long', day: 'numeric', month: 'long'});
  return `<div class="datebar"><button class="btn small secondary" type="button" aria-label="Día anterior" onclick="shiftDay(-1)">‹</button><label class="datebar-pick"><b>${isToday ? 'Hoy' : esc(long)}</b>${isToday ? `<small>${esc(long)}</small>` : ''}<input id="dashDate" type="date" value="${esc(d)}" aria-label="Elegir día" onchange="setSelectedDate(this.value);render()"></label><button class="btn small secondary" type="button" aria-label="Día siguiente" onclick="shiftDay(1)" ${isToday ? 'disabled' : ''}>›</button>${isToday ? '' : '<button class="btn small" type="button" onclick="setSelectedDate(today());render()">Hoy</button>'}</div>`;
}
function mealCard(m) {
  return `<article class="list-card"><header><div><h4>${esc(m.date)} · ${esc(m.time)} · ${esc(m.name)}</h4><p class="muted">${esc(m.notes || '')}</p></div><div class="card-actions"><button class="btn small secondary" title="Repetir hoy" onclick="repeatMeal(${Number(m.id)}, this)">↻</button><button class="btn small danger" onclick="deleteMeal(${Number(m.id)})">×</button></div></header><div class="chips">${(m.items || []).map((i) => `<span class="chip">${esc(i.food_name)} ${fmt(i.grams)}g</span>`).join('')}</div><b>${fmt(m.totals?.kcal)} kcal · ${fmt(m.totals?.protein)} g prot.</b></article>`;
}
function workoutCard(w) {
  return `<article class="list-card"><header><div><h4>${esc(w.date)} · ${esc(w.time)} · ${esc(w.name)}</h4><p class="muted">${fmt(w.minutes)} min ${w.distance_km ? `· ${fmt(w.distance_km)} km` : ''} · ${esc(cleanWorkoutNote(w.notes))}</p></div><button class="btn small danger" onclick="deleteWorkout(${Number(w.id)})">×</button></header><b>${fmt(w.kcal)} kcal</b></article>`;
}
function cleanWorkoutNote(n) { return window.DPPDashboardWorkoutCard.cleanNote(n); }
function mealCardCompact(m) { return window.DPPDashboardMealCard.mealCardCompact(m); }
function workoutCardCompact(w) { return window.DPPDashboardWorkoutCard.workoutCardCompact(w); }
async function deleteMeal(id) { if (!confirm('¿Borrar comida?')) return; await api('/api/meals/' + id, {method: 'DELETE'}); toast('Comida borrada'); await load(); }
async function deleteWorkout(id) { if (!confirm('¿Borrar entreno?')) return; await api('/api/workouts/' + id, {method: 'DELETE'}); toast('Entreno borrado'); await load(); }
async function repeatMeal(id, btn) {
  await busy(btn, async () => { await api(`/api/meals/${Number(id)}/duplicate`, {method: 'POST', body: JSON.stringify({date: today(), time: nowHM()})}); toast('Comida repetida hoy'); setSelectedDate(today()); await load(); });
}

/* ---------- Registrar comida ---------- */
function templateOptions() { return state.templates.map((t) => `<option value="${Number(t.id)}">${esc(t.name)}</option>`).join(''); }
function renderRegister() {
  mealItems = [];
  $('#view').innerHTML = `<div class="register-grid">
    <section class="card register-main">
      <div class="section-title compact-title"><div><h3>🍽️ Nueva comida</h3><p>1) carga plantilla o busca alimentos · 2) cambia gramos · 3) guarda</p></div></div>
      <div class="row">
        <div class="field span-3"><label>Fecha</label><input id="mDate" type="date" value="${esc(day())}"></div>
        <div class="field span-2"><label>Hora</label><input id="mTime" type="time" value="${esc(nowHM())}"></div>
        <div class="field span-3"><label>Tipo</label><select id="mName"><option>Desayuno</option><option>Pre-comida</option><option>Comida</option><option>Merienda</option><option>Cena</option><option>Post-entreno</option></select></div>
        <div class="field span-4"><label>Notas</label><input id="mNotes" placeholder="pasta seca, tupper, post-HIIT..."></div>
      </div>
      <div class="template-loader">
        <div><b>⚡ Cargar plantilla</b><small>Se añade a esta comida y puedes cambiar gramos antes de guardar.</small></div>
        <select id="tplSelect"><option value="">Elegir plantilla...</option>${templateOptions()}</select>
        <button class="btn secondary" onclick="loadTemplateToMeal($('#tplSelect').value)">Cargar</button>
      </div>
      <div id="mealBuilder" class="meal-items"></div>
      <div class="sticky-actions">
        <button class="btn" onclick="saveMeal(this)">Guardar comida</button>
        <button class="btn secondary" onclick="saveMealAsTemplate()">Guardar como plantilla</button>
        <button class="btn secondary" onclick="clearMeal()">Limpiar</button>
      </div>
    </section>
    <section class="card add-food-panel" aria-label="Añadir producto">
      <h3>➕ Añadir producto</h3>
      <div class="field"><label>Buscar alimento guardado</label><input id="foodSearch" placeholder="pollo, pasta, yogur..." autocomplete="off" oninput="renderSuggestions()" onkeydown="if(event.key==='Enter'){event.preventDefault();this.closest('.add-food-panel').querySelector('.suggestions button')?.click()}"></div>
      <div class="field" style="margin-top:10px"><label>Gramos</label><input id="foodGrams" type="number" inputmode="decimal" min="0" placeholder="ración típica"></div>
      <div id="suggestions" class="suggestions"></div>
      <p class="muted">Tip: si es una plantilla, cárgala y cambia solo gramos. Enter añade el primer resultado.</p>
    </section>
  </div>`;
  renderMealBuilder(); renderSuggestions();
}
function normText(v) { return String(v || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); }
/* Restored in v0.1.0: the search list was referenced but never defined, so food search threw. */
function renderSuggestions() {
  const box = $('#suggestions'); if (!box || !state) return;
  const terms = normText($('#foodSearch')?.value).split(/\s+/).filter(Boolean);
  const scored = state.foods.map((f) => {
    const hay = normText(`${f.name} ${f.brand || ''}`);
    if (terms.length && !terms.every((t) => hay.includes(t))) return null;
    const starts = terms.length && normText(f.name).startsWith(terms[0]) ? 2 : 0;
    return {f, score: starts + (Number(f.purchased) ? 1 : 0)};
  }).filter(Boolean).sort((a, b) => b.score - a.score || a.f.name.localeCompare(b.f.name, 'es')).slice(0, terms.length ? 12 : 6);
  box.innerHTML = (terms.length ? '' : '<small class="muted">Frecuentes · escribe para buscar en todo el catálogo</small>') + (scored.length ? scored.map(({f}) => `<button type="button" onclick="addFood(${Number(f.id)})"><b>${Number(f.purchased) ? '✅ ' : ''}${esc(f.name)}</b><br><small class="muted">${fmt(f.kcal)} kcal · ${fmt(f.protein)} g prot /100 g · ración ${fmt(f.typical_g)} g${f.brand ? ' · ' + esc(f.brand) : ''}</small></button>`).join('')
    : `<div class="empty">Sin resultados. Créalo en <a href="#" onclick="go('foods');return false">Alimentos</a> (OCR, código de barras o manual).</div>`);
}
function loadTemplateToMeal(id) {
  if (!id) { toast('Elige una plantilla'); return; }
  const t = state.templates.find((x) => String(x.id) === String(id));
  if (!t) { toast('Plantilla no encontrada'); return; }
  let p = {items: []}; try { p = JSON.parse(t.payload); } catch (e) { /* keep empty */ }
  const missing = [];
  mealItems = (p.items || []).map((it) => { const f = foodByName(it.food); if (!f) missing.push(it.food); return f ? calcFood(f, it.grams) : null; }).filter(Boolean);
  if ($('#mNotes') && !$('#mNotes').value) $('#mNotes').value = t.notes || '';
  renderMealBuilder(); toast(missing.length ? `Plantilla cargada; faltan en el catálogo: ${missing.join(', ')}` : 'Plantilla cargada: cambia gramos y guarda');
}
function addFood(id) {
  const f = foodById(id); if (!f) { toast('Ese alimento no está disponible; recarga la página'); return; }
  const g = Number($('#foodGrams').value || f.typical_g || 100);
  mealItems.push(calcFood(f, g)); $('#foodSearch').value = ''; $('#foodGrams').value = '';
  renderMealBuilder(); renderSuggestions(); $('#foodSearch')?.focus();
}
function renderMealBuilder() {
  const advice = mealAdvice(mealItems);
  $('#mealBuilder').innerHTML = `${mealItems.length ? mealItems.map((it, idx) => `<div class="item-row"><div><b>${esc(it.food_name)}</b><small>${fmt(it.kcal)} kcal · ${fmt(it.protein)} g prot.</small></div><input type="number" inputmode="decimal" min="0" value="${Number(it.grams)}" aria-label="Gramos de ${esc(it.food_name)}" onchange="changeMealGram(${idx},this.value)"><button class="btn small danger" onclick="removeMealItem(${idx})">×</button></div>`).join('') : '<div class="empty">Busca un producto y añádelo. Después solo cambias gramos.</div>'}<div class="totals"><span class="pill ${advice.cls}">${advice.label}</span><b>${fmt(advice.t.kcal)} kcal</b><b>${fmt(advice.t.protein)} g proteína</b><span class="muted">${advice.text}</span></div>`;
}
function changeMealGram(idx, val) { const f = foodById(mealItems[idx].food_id); if (f) mealItems[idx] = calcFood(f, Number(val || 0)); renderMealBuilder(); }
function removeMealItem(idx) { mealItems.splice(idx, 1); renderMealBuilder(); }
function clearMeal() { mealItems = []; renderMealBuilder(); }
async function saveMeal(btn) {
  if (!mealItems.length) { toast('Añade alimentos'); return; }
  await busy(btn, async () => {
    await api('/api/meals', {method: 'POST', body: JSON.stringify({date: $('#mDate').value, time: $('#mTime').value, name: $('#mName').value, notes: $('#mNotes').value, items: mealItems.map((i) => ({food_id: i.food_id, food_name: i.food_name, grams: i.grams}))})});
    toast('Comida guardada'); setSelectedDate($('#mDate').value); mealItems = []; await load(); go('home');
  });
}
async function saveWeight(btn) {
  await busy(btn, async () => {
    const r = await api('/api/weights', {method: 'POST', body: JSON.stringify({date: $('#wDate').value, time: $('#wTime').value, kg: $('#wKg').value, official: $('#wOfficial').value === '1', context: $('#wCtx').value})});
    toast(r.duplicate ? 'Ese peso ya estaba registrado' : 'Peso guardado'); await load(); go('weights');
  });
}
async function saveMealAsTemplate() {
  if (!mealItems.length) { toast('Añade alimentos primero'); return; }
  const name = prompt('Nombre de plantilla'); if (!name) return;
  try { await api('/api/templates', {method: 'POST', body: JSON.stringify({name, notes: $('#mNotes').value, kind: 'meal', payload: {items: mealItems.map((i) => ({food: i.food_name, grams: i.grams}))}})}); toast('Plantilla guardada'); await load(); } catch (e) { toast(e.message); }
}

/* ---------- Plantillas ---------- */
function templateItems(t) { let p = {items: []}; try { p = JSON.parse(t.payload); } catch (e) { /* keep empty */ } return (p.items || []).map((it) => { const f = foodByName(it.food); return f ? calcFood(f, it.grams) : null; }).filter(Boolean); }
function renderTemplates() { $('#view').innerHTML = `<p class="muted page-hint">Cambia los gramos y guarda la comida en dos toques.</p><div class="grid cols-2">${state.templates.map(templateCard).join('') || '<div class="empty">Aún no hay plantillas: créalas desde Registrar con «Guardar como plantilla».</div>'}</div>`; }
function templateCard(t) {
  const items = templateItems(t); const total = calcList(items);
  return `<div class="card template-card" data-template="${Number(t.id)}"><h3>${esc(t.name)}</h3><p class="muted">${esc(t.notes || '')}</p><div class="template-items">${items.map((it, idx) => `<div class="template-item"><div><b>${esc(it.food_name)}</b><br><small>${fmt(it.kcal)} kcal · ${fmt(it.protein)} g prot.</small></div><input type="number" inputmode="decimal" value="${Number(it.grams)}" data-tgram="${idx}" data-food="${esc(it.food_name)}"></div>`).join('')}</div><div class="totals"><b>${fmt(total.kcal)} kcal</b><b>${fmt(total.protein)} g prot.</b></div><button class="btn" onclick="saveTemplateMeal(${Number(t.id)}, this)">Guardar ahora</button></div>`;
}
async function saveTemplateMeal(id, btn) {
  const t = state.templates.find((x) => Number(x.id) === Number(id)); const card = document.querySelector(`[data-template="${Number(id)}"]`);
  const items = [...card.querySelectorAll('[data-tgram]')].map((i) => ({food_name: i.dataset.food, grams: Number(i.value)}));
  if (!items.length) { toast('La plantilla no tiene alimentos del catálogo'); return; }
  await busy(btn, async () => { await api('/api/meals', {method: 'POST', body: JSON.stringify({date: day(), time: nowHM(), name: t.name, notes: t.notes, items})}); toast('Plantilla registrada'); await load(); go('home'); });
}

/* ---------- Alimentos ---------- */
function renderFoods() {
  selectedFoodPhoto = '';
  $('#view').innerHTML = `<div class="grid cols-2">
    <div class="card"><h3>🥫 Nuevo alimento</h3>
      <div id="foodLookup"></div>
      <div class="photo-box"><div><b>📷 Foto etiqueta</b><small>OCR real local: sube foto, revisa las sugerencias y guarda.</small></div><input id="fPhoto" type="file" accept="image/*" onchange="uploadFoodPhoto()"><div id="photoPreview"></div></div>
      <div class="row">
        <div class="field span-6"><label>Nombre</label><input id="fName" placeholder="Ej. Yogur Eroski +Proteína 120 g"></div>
        <div class="field span-6"><label>Marca</label><input id="fBrand" placeholder="Eroski, ElPozo..."></div>
        <div class="field span-3"><label>kcal / 100 g</label><input id="fKcal" type="number" inputmode="decimal"></div>
        <div class="field span-3"><label>proteína / 100 g</label><input id="fProt" type="number" inputmode="decimal"></div>
        <div class="field span-3"><label>hidratos</label><input id="fCarbs" type="number" inputmode="decimal"></div>
        <div class="field span-3"><label>grasa</label><input id="fFat" type="number" inputmode="decimal"></div>
        <div class="field span-3"><label>azúcar</label><input id="fSugar" type="number" inputmode="decimal"></div>
        <div class="field span-3"><label>sal</label><input id="fSalt" type="number" inputmode="decimal"></div>
        <div class="field span-3"><label>ración g</label><input id="fTypical" type="number" inputmode="decimal" value="100"></div>
        <div class="field span-3"><label>Comprado</label><select id="fPurchased"><option value="1">Sí</option><option value="0">No</option></select></div>
        <input id="fBarcode" type="hidden">
        <div class="field span-12"><label>Nota etiqueta</label><textarea id="fSource" placeholder="Ej. Por unidad 120 g: 68 kcal, 10 g proteína..."></textarea></div>
        <div class="field span-12"><label>Uso</label><input id="fNotes" placeholder="Desayuno, merienda, tupper..."></div>
      </div>
      <button class="btn" onclick="saveFood(this)">Guardar alimento</button>
    </div>
    <div class="card note-box"><h3>📌 Tres formas de añadir</h3><p><b>Código de barras</b>: busca en Open Food Facts (base abierta) y rellena todo.</p><p><b>Foto de etiqueta</b>: OCR local con Tesseract; si configuras IA, también lectura con IA.</p><p class="muted">Revisa siempre los valores antes de guardar. Guardar con un nombre existente actualiza ese alimento.</p></div>
  </div>
  <div class="section-title"><div><h3>Alimentos guardados</h3><p>Se usan en Registrar para cambiar solo gramos.</p></div><input id="foodFilter" placeholder="filtrar..." style="max-width:300px" oninput="renderFoodList()"></div>
  <div id="foodList" class="grid cols-3"></div>`;
  renderFoodList();
  window.DPPFoodLookup?.mount('#foodLookup');
}
function renderFoodList() {
  const q = normText($('#foodFilter')?.value);
  const foods = state.foods.filter((f) => normText(`${f.name} ${f.brand} ${f.source_note}`).includes(q));
  $('#foodList').innerHTML = (foods.slice(0, listLimit('foods')).map((f) => `<div class="card food-card">${/^\/uploads\/[\w.-]+$/.test(f.photo_path || '') ? `<img class="food-photo" src="${esc(f.photo_path)}" alt="foto etiqueta" loading="lazy">` : ''}<h3>${Number(f.purchased) ? '✅' : '🥫'} ${esc(f.name)}</h3><p class="muted">${esc(f.brand || '')}${f.barcode ? ' · ' + esc(f.barcode) : ''}</p><div class="chips"><span class="chip">${fmt(f.kcal)} kcal/100g</span><span class="chip">${fmt(f.protein)} g prot</span><span class="chip">típico ${fmt(f.typical_g)} g</span></div><p class="source">${esc(f.source_note || '')}</p><p>${esc(f.notes || '')}</p><div class="card-actions"><button class="btn small secondary" onclick="editFood(${Number(f.id)})">Editar</button><button class="btn small danger" onclick="deleteFood(${Number(f.id)})">Borrar</button></div></div>`).join('') || '<div class="empty">Sin alimentos con ese filtro.</div>') + moreButton('foods', foods.length);
}
function fillFoodForm(food) {
  const set = (id, val) => { const el = $(id); if (el && val !== undefined && val !== null) el.value = String(val); };
  set('#fName', food.name); set('#fBrand', food.brand); set('#fKcal', food.kcal); set('#fProt', food.protein); set('#fCarbs', food.carbs);
  set('#fFat', food.fat); set('#fSugar', food.sugar); set('#fSalt', food.salt); set('#fTypical', food.typical_g || 100);
  set('#fSource', food.source_note); set('#fNotes', food.notes); set('#fBarcode', food.barcode || '');
  if (food.purchased !== undefined) set('#fPurchased', Number(food.purchased) ? '1' : '0');
  if (food.photo_path) selectedFoodPhoto = food.photo_path;
}
function editFood(id) { const f = foodById(id); if (!f) return; selectedFoodPhoto = f.photo_path || ''; fillFoodForm(f); $('#fName')?.scrollIntoView({behavior: 'smooth', block: 'center'}); toast('Edita y guarda (mismo nombre = actualizar)'); }
async function deleteFood(id) { const f = foodById(id); if (!f || !confirm(`¿Borrar "${f.name}" del catálogo? Las comidas ya registradas no cambian.`)) return; try { await api('/api/foods/' + Number(id), {method: 'DELETE'}); toast('Alimento borrado'); await load(); } catch (e) { toast(e.message); } }
function ocr3Set(id, val) { const el = document.querySelector(id); if (!el || val === undefined || val === null || val === '') return; el.value = String(val).replace(',', '.'); }
function ocr3Badge(text, cls = 'info') { return `<span class="ocr3-badge ${cls}">${esc(text)}</span>`; }
function applyLabelResult(r) {
  selectedFoodPhoto = r.photo_path || selectedFoodPhoto;
  const n = r.nutrition || {}; const product = r.product || {}; const serving = r.serving || {}; const extra = r.extra || {}; const warnings = r.warnings || []; const conf = r.confidence || 'baja';
  if (product.name) $('#fName').value = product.name;
  if (product.brand) $('#fBrand').value = product.brand;
  ocr3Set('#fKcal', n.kcal); ocr3Set('#fProt', n.protein); ocr3Set('#fCarbs', n.carbs); ocr3Set('#fFat', n.fat); ocr3Set('#fSugar', n.sugar); ocr3Set('#fSalt', n.salt);
  ocr3Set('#fTypical', n.typical_g || product.typical_g || serving.grams);
  const parts = [`${r.engine === 'ai' ? 'Lectura con IA' : `OCR ${r.ocr_engine || 'local'} · modo ${r.ocr_mode || '-'}`} · confianza ${conf}${r.cache_hit || r.cached ? ' · cache' : ''}.`];
  if (product.name) parts.push(`Producto: ${product.name}${product.brand ? ' · ' + product.brand : ''}.`);
  if (serving.grams) parts.push(`Ración etiqueta ${serving.grams} g: ${serving.kcal ?? '-'} kcal · ${serving.protein ?? '-'} g prot · ${serving.fat ?? '-'} g grasa · ${serving.salt ?? '-'} g sal.`);
  if (extra.saturated !== undefined || extra.calcium_mg !== undefined) parts.push(`Extra por 100 g: saturadas ${extra.saturated ?? '-'} g · calcio ${extra.calcium_mg ?? '-'} mg.`);
  if (warnings.length) parts.push(`Avisos: ${warnings.slice(0, 5).join(' | ')}`);
  if (r.ocr_text) parts.push(r.ocr_text.length > 650 ? r.ocr_text.slice(0, 650) + '…' : r.ocr_text);
  $('#fSource').value = parts.join('\n\n');
  const cls = conf === 'alta' ? 'good' : conf === 'media' ? 'info' : conf === 'baja' ? 'warn' : 'bad';
  const preview = $('#photoPreview');
  if (preview) preview.innerHTML = `${/^\/uploads\/[\w.-]+$/.test(selectedFoodPhoto) ? `<img class="food-photo preview" src="${esc(selectedFoodPhoto)}" alt="foto etiqueta">` : ''}<div class="ocr3-status">${ocr3Badge('foto guardada', 'good')}${ocr3Badge(r.engine === 'ai' ? 'IA' : (r.cache_hit ? 'OCR desde cache' : 'OCR leído'), 'good')}${ocr3Badge('confianza ' + conf, cls)}<small>Campos: ${esc(Object.keys(n).join(', ') || 'sin valores seguros')}</small>${warnings[0] ? `<small class="ocr3-warn">${esc(warnings[0])}</small>` : ''}<span id="aiLabelSlot"></span></div>`;
  window.DPPAICoach?.offerLabel?.('#aiLabelSlot', selectedFoodPhoto, conf);
}
async function uploadFoodPhoto() {
  const file = $('#fPhoto')?.files?.[0]; if (!file) return;
  const preview = $('#photoPreview'); if (preview) preview.innerHTML = ocr3Badge('leyendo OCR...', 'info');
  const form = new FormData(); form.append('photo', file);
  try { const r = await apiForm('/api/food-photo-ocr', form); applyLabelResult(r); toast(r.cache_hit ? 'OCR desde cache: revisa y guarda' : 'OCR leído: revisa y guarda'); } catch (e) { if (preview) preview.innerHTML = ocr3Badge('error OCR', 'bad'); toast(e.message || 'Error OCR'); }
}
async function saveFood(btn) {
  await busy(btn, async () => {
    await api('/api/foods', {method: 'POST', body: JSON.stringify({name: $('#fName').value, brand: $('#fBrand').value, kcal: $('#fKcal').value, protein: $('#fProt').value, carbs: $('#fCarbs').value, fat: $('#fFat').value, sugar: $('#fSugar').value, salt: $('#fSalt').value, typical_g: $('#fTypical').value, purchased: $('#fPurchased').value === '1', source_note: $('#fSource').value, notes: $('#fNotes').value, photo_path: selectedFoodPhoto, barcode: $('#fBarcode')?.value || ''})});
    toast('Alimento guardado'); await load(); go('foods');
  });
}

/* ---------- Deporte ---------- */
function ui5SportCard(w) {
  return `<article class="ui5-sport-card"><div class="ui5-sport-head"><div><b>${esc(w.name || 'Entreno')}</b><small>${esc(w.date || '')} · ${esc(w.time || '')}</small></div><button class="btn small danger" onclick="deleteWorkout(${Number(w.id)})">×</button></div><div class="ui5-sport-metrics"><span><b>${fmt(w.minutes)}</b><small>min</small></span><span><b>${fmt(w.distance_km)}</b><small>km</small></span><span><b>${fmt(w.kcal)}</b><small>kcal</small></span></div><p>${esc(cleanWorkoutNote(w.notes))}</p></article>`;
}
function renderSport() {
  const all = [...state.workouts].sort((a, b) => (b.date + b.time).localeCompare(a.date + a.time));
  const last7 = all.filter((w) => Date.now() - new Date(w.date + 'T12:00:00').getTime() <= 7 * 86400000);
  const sum = (k) => last7.reduce((a, w) => a + Number(w[k] || 0), 0);
  $('#view').innerHTML = `
    <section class="ui5-sport-hero"><div><span class="ui5-kicker">Deporte</span><h3>Registrar o revisar actividad</h3><p>Strava queda como fuente principal; el manual sirve para ajustes rápidos.</p></div>
      <div class="ui5-sport-summary"><span><b>${fmt(sum('kcal'))}</b><small>kcal 7 días</small></span><span><b>${fmt(sum('minutes'))}</b><small>min 7 días</small></span><span><b>${fmt(sum('distance_km'))}</b><small>km 7 días</small></span></div></section>
    <div class="ui5-sport-layout">
      <div class="card ui5-sport-form"><h3>🏋️ Nuevo entreno</h3><div class="row compact-row">
        <div class="field span-3"><label>Fecha</label><input id="sDate" type="date" value="${esc(day())}"></div>
        <div class="field span-2"><label>Hora</label><input id="sTime" type="time" value="${esc(nowHM())}"></div>
        <div class="field span-4"><label>Ejercicio</label><select id="sName">${state.exercises.map((e) => `<option>${esc(e.name)}</option>`).join('')}</select></div>
        <div class="field span-3"><label>Minutos</label><input id="sMin" type="number" inputmode="decimal"></div>
        <div class="field span-3"><label>Distancia km</label><input id="sKm" type="number" step="0.01" inputmode="decimal"></div>
        <div class="field span-3"><label>Calorías reloj</label><input id="sKcal" type="number" inputmode="decimal" placeholder="vacío = estima"></div>
        <div class="field span-6"><label>Notas</label><input id="sNotes" placeholder="Strava, reloj, sensación, etc."></div>
        <div class="field span-3"><label>&nbsp;</label><button class="btn" onclick="saveWorkout(this)">Guardar entreno</button></div>
      </div></div>
      <div class="card ui5-exercise-form"><h3>➕ Tipo ejercicio</h3><p class="muted">Añade solo si falta un tipo manual. Para Strava no hace falta.</p><div class="row compact-row">
        <div class="field span-6"><label>Nombre</label><input id="eName" placeholder="Ej. Caminata suave"></div>
        <div class="field span-3"><label>MET</label><input id="eMet" type="number" value="5"></div>
        <div class="field span-3"><label>&nbsp;</label><button class="btn secondary" onclick="saveExercise(this)">Guardar</button></div>
        <div class="field span-12"><label>Notas</label><input id="eNotes"></div>
      </div></div>
    </div>
    <div class="section-title ui5-section-title"><div><h3>Historial deporte</h3><p>${all.length} entrenos · últimos primero</p></div></div>
    <div class="ui5-sport-history">${all.slice(0, listLimit('sport')).map(ui5SportCard).join('')}</div>${moreButton('sport', all.length)}`;
}
async function saveWorkout(btn) {
  await busy(btn, async () => {
    const r = await api('/api/workouts', {method: 'POST', body: JSON.stringify({date: $('#sDate').value, time: $('#sTime').value, name: $('#sName').value, minutes: $('#sMin').value, distance_km: $('#sKm').value, kcal: $('#sKcal').value, notes: $('#sNotes').value})});
    toast(r.id ? `Entreno guardado · ${fmt(r.kcal)} kcal` : 'Ese entreno ya existía'); setSelectedDate($('#sDate').value); await load(); go('home');
  });
}
async function saveExercise(btn) { await busy(btn, async () => { await api('/api/exercises', {method: 'POST', body: JSON.stringify({name: $('#eName').value, met: $('#eMet').value, notes: $('#eNotes').value})}); toast('Ejercicio guardado'); await load(); go('sport'); }); }

/* ---------- Peso ---------- */
function ui5OfficialWeights() { return state.weights.filter((w) => w.official).sort((a, b) => (a.date + a.time).localeCompare(b.date + b.time)); }
function ui5Trend() {
  const ws = ui5OfficialWeights(); if (ws.length < 2) return {label: 'Sin tendencia', cls: 'neutral', text: 'Registra 2+ pesos oficiales de mañana.'};
  const f = ws[0], l = ws.at(-1), days = Math.max(1, (new Date(l.date) - new Date(f.date)) / 86400000), delta = Number(l.kg) - Number(f.kg);
  if (days < 7 || ws.length < 5) return {label: delta < 0 ? 'Bajada inicial' : delta > 0 ? 'Subida inicial' : 'Estable', cls: 'info', text: `${fmt(delta)} kg desde ${f.date}. Pocos días: sin extrapolar kg/semana.`};
  const weekly = delta / days * 7; const text = `${fmt(delta)} kg · ${fmt(weekly)} kg/sem aprox.`;
  if (weekly < -1) return {label: 'Bajada rápida', cls: 'warn', text};
  if (weekly < -0.35) return {label: 'Bajada correcta', cls: 'good', text};
  if (delta > 0) return {label: 'Subiendo', cls: 'bad', text};
  return {label: 'Estable', cls: 'info', text};
}
function weightChart() {
  const ws = ui5OfficialWeights().slice(-14); if (ws.length < 2) return '<div class="empty">Cuando tengas 2+ pesos oficiales aparece la gráfica.</div>';
  const vals = ws.map((w) => Number(w.kg)), min = Math.min(...vals) - 0.25, max = Math.max(...vals) + 0.25, W = 640, H = 280, L = 68, R = 32, T = 42, B = 56, pw = W - L - R, ph = H - T - B;
  const x = (i) => L + i * (pw / (ws.length - 1)), y = (v) => T + (max - v) / (max - min) * ph;
  const pts = ws.map((w, i) => `${x(i)},${y(Number(w.kg))}`).join(' ');
  const ticks = [min, (min + max) / 2, max].map((v) => `<line x1="${L}" y1="${y(v)}" x2="${W - R}" y2="${y(v)}" stroke="rgba(31,60,90,.13)"/><text x="14" y="${y(v) + 5}" font-size="13" font-weight="800" fill="#314964">${fmt(v)}</text>`).join('');
  const dots = ws.map((w, i) => `<g><circle cx="${x(i)}" cy="${y(Number(w.kg))}" r="6" fill="#2563eb" stroke="#fff" stroke-width="2"/>${i === ws.length - 1 || i === 0 ? `<text x="${x(i)}" y="${y(Number(w.kg)) - 14}" text-anchor="middle" font-size="13" font-weight="900" fill="#0b1726">${fmt(w.kg)}</text>` : ''}<title>${esc(w.date)} ${esc(w.time)}: ${fmt(w.kg)} kg</title></g>`).join('');
  const tr = ui5Trend();
  return `<div class="ui5-chartbox"><svg class="chart ui5-weight-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Peso oficial reciente">${ticks}<polyline points="${pts}" fill="none" stroke="#2563eb" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>${dots}<text x="${L}" y="${H - 18}" font-size="13" font-weight="800" fill="#54677f">${esc(ws[0].date)}</text><text x="${W - R}" y="${H - 18}" text-anchor="end" font-size="13" font-weight="800" fill="#54677f">${esc(ws.at(-1).date)}</text></svg><div class="ui5-trend"><span class="ui5-chip ${tr.cls}">${esc(tr.label)}</span><b>${esc(tr.text)}</b></div></div>`;
}
/* Long lists render 30 rows; "Ver más" adds 30 more (phones choked on 20 000 px pages). */
const LIST_LIMITS = {};
function listLimit(key) { return LIST_LIMITS[key] || 30; }
function moreButton(key, total) { const shown = listLimit(key); return total > shown ? `<button class="btn secondary more-btn" type="button" onclick="LIST_LIMITS['${key}']=${shown + 30};render()">Ver más (${total - shown})</button>` : ''; }
function renderWeights() {
  const all = [...state.weights].sort((a, b) => (b.date + b.time).localeCompare(a.date + a.time));
  $('#view').innerHTML = `<div class="grid cols-2"><div class="card weight-form"><h3>Registrar peso</h3>
      <div class="row compact-row"><div class="field span-6"><label>Kg</label><input id="wKg" type="number" step="0.01" inputmode="decimal" placeholder="kg de hoy"></div><div class="field span-6"><label>Tipo</label><select id="wOfficial"><option value="1">Oficial (mañana)</option><option value="0">Referencia</option></select></div></div>
      <details class="more-fields"><summary>Fecha, hora y contexto</summary><div class="row compact-row"><div class="field span-6"><label>Fecha</label><input id="wDate" type="date" value="${esc(today())}"></div><div class="field span-6"><label>Hora</label><input id="wTime" type="time" value="${esc(nowHM())}"></div><div class="field span-12"><label>Contexto</label><input id="wCtx" placeholder="mañana, después del baño"></div></div></details>
      <button class="btn block" onclick="saveWeight(this)">Guardar peso</button></div>
    <div class="card"><h3>Peso oficial</h3>${weightChart()}<p class="muted small-note">Solo pesos oficiales. Más detalle en <a href="#" onclick="go('progress');return false">Progreso</a>.</p></div></div>
    <div class="section-title"><div><h3>Historial</h3><p>${all.length} registros</p></div></div><div class="list">${all.slice(0, listLimit('weights')).map((w) => `<div class="list-card row-card"><div><b>${fmt(w.kg)} kg</b><small class="muted">${esc(w.date)} ${esc(w.time)} · ${w.official ? 'oficial' : 'referencia'}${w.context ? ' · ' + esc(w.context) : ''}</small></div><button class="btn small danger" aria-label="Borrar peso" onclick="deleteWeight(${Number(w.id)})">×</button></div>`).join('')}</div>${moreButton('weights', all.length)}`;
}
async function deleteWeight(id) { if (!confirm('¿Borrar peso?')) return; await api('/api/weights/' + id, {method: 'DELETE'}); toast('Peso borrado'); await load(); }

function renderHistory() { $('#view').innerHTML = `<div class="grid cols-2"><div><div class="section-title"><div><h3>Comidas</h3><p>${state.meals.length} registradas · ↻ repite una comida hoy</p></div></div><div class="list">${state.meals.slice(0, listLimit('hmeals')).map(mealCard).join('')}</div>${moreButton('hmeals', state.meals.length)}</div><div><div class="section-title"><div><h3>Deporte</h3><p>${state.workouts.length} entrenos</p></div></div><div class="list">${state.workouts.slice(0, listLimit('hwork')).map(workoutCard).join('')}</div>${moreButton('hwork', state.workouts.length)}</div></div>`; }
function renderIntegrations() { $('#view').innerHTML = '<div class="empty">Cargando integraciones…</div>'; }

/* ---------- Shell ---------- */
function linkFieldLabels() {
  // Templates write <div class="field"><label>Kg</label><input>…>: tie them so tapping the label focuses the input.
  document.querySelectorAll('#view .field').forEach((f, i) => {
    const l = f.querySelector(':scope > label'), c = f.querySelector('input, select, textarea');
    if (!l || !c || l.htmlFor) return;
    if (!c.id) c.id = `f-${page}-${i}`;
    l.htmlFor = c.id;
  });
  // Controls without a visible label still get an accessible name.
  const named = {tplSelect: 'Plantilla', fPhoto: 'Foto de la etiqueta', pantryNewCategory: 'Categoría', planRaw: 'JSON del plan'};
  document.querySelectorAll('#view input:not([type=hidden]), #view select, #view textarea').forEach((c) => {
    if (c.labels?.length || c.getAttribute('aria-label')) return;
    const name = c.dataset.food ? `Gramos de ${c.dataset.food}` : c.dataset.planField === 'day' ? 'Nombre del día' : c.dataset.planField === 'status' ? 'Estado del día' : (named[c.id] || c.placeholder || '');
    if (name) c.setAttribute('aria-label', name);
  });
}
function ui5ApplyShell() {
  linkFieldLabels();
  document.documentElement.dataset.ui = 'ui5';
  const version = window.DPP_VERSION || '';
  const e = document.querySelector('.eyebrow'); if (e) e.textContent = `Dieta controlada${version ? ' · ' + version : ''}`;
  const r = document.querySelector('.rule-banner');
  if (r && r.dataset.ui5 !== '1') { r.dataset.ui5 = '1'; r.innerHTML = '<article class="ui5-rule protein"><span>Proteína</span><b id="ruleProtein">130–150 g/día</b><small>Prioridad antes de recortar de más.</small></article><article class="ui5-rule oil"><span>Aceite</span><b id="ruleOil">5 g normal · 10 g máximo</b><small>Medido, no a ojo.</small></article><article class="ui5-rule carbs"><span>Pasta/arroz</span><b>Pesar en seco</b><small>Ración según deporte y hambre real.</small></article>'; }
  const sr = document.querySelector('.sidebar .side-rule');
  if (sr && sr.dataset.ui5 !== '1') { sr.dataset.ui5 = '1'; sr.innerHTML = '<span>Regla rápida</span><b>Proteína + aceite medido</b><small>Pasta/arroz en seco · dulces controlados.</small>'; }
  if (!document.getElementById('btnHelp')) { const h = document.createElement('button'); h.id = 'btnHelp'; h.className = 'ghost'; h.type = 'button'; h.textContent = 'Ayuda'; h.onclick = openHelpModal; document.querySelector('.top-actions')?.prepend(h); }
}
function openHelpModal() {
  closeHelpModal(); const o = document.createElement('div'); o.id = 'helpOverlay'; o.className = 'help-overlay';
  o.innerHTML = `<div class="help-modal" role="dialog" aria-modal="true" aria-label="Ayuda"><button class="help-close" onclick="closeHelpModal()" aria-label="Cerrar">×</button><span class="ui5-kicker">Ayuda rápida</span><h2>Diet Pro Planner</h2><div class="help-grid"><div><b>🍽️ Comidas</b><p>Busca alimentos o carga una plantilla, cambia gramos y guarda. ↻ repite una comida.</p></div><div><b>⚖️ Peso</b><p>Oficial por la mañana. Post-comida, noche o post-entreno son referencia.</p></div><div><b>📈 Progreso</b><p>Tendencia real, ritmo kg/semana y tu gasto energético medido con tus propios datos.</p></div><div><b>🥫 Alimentos</b><p>Código de barras (Open Food Facts), OCR de etiqueta o IA opcional.</p></div><div><b>🎯 Objetivos</b><p>Tus metas de peso, kcal y proteína. Copias de seguridad y exportación.</p></div><div><b>🔐 Privacidad</b><p>Todo se guarda en tu Raspberry. La IA y Open Food Facts son opcionales.</p></div></div><div class="help-actions"><button class="btn" onclick="closeHelpModal();go('register')">Registrar comida</button><button class="btn secondary" onclick="closeHelpModal();go('progress')">Progreso</button><button class="btn secondary" onclick="closeHelpModal();go('goals')">Objetivos</button></div></div>`;
  o.onclick = (ev) => { if (ev.target.id === 'helpOverlay') closeHelpModal(); }; document.body.appendChild(o);
}
function closeHelpModal() { document.getElementById('helpOverlay')?.remove(); }
document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape') closeHelpModal(); });

$('#btnRefresh').onclick = () => load().then(() => toast('Datos actualizados')).catch((e) => toast(e.message));
// Start after every module script has registered its pages/renderers.
// Offline shell (static/sw.js): network first, last copy when the Raspberry is unreachable.
if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => { /* http on some browsers */ });
window.addEventListener('offline', () => toast('Sin conexión: ves los últimos datos guardados'));
window.addEventListener('online', () => { toast('Conexión recuperada'); flushQueue().then(() => load()).catch(() => {}); });
// Home-screen shortcuts open a page directly: /?page=register|weights|progress
function openStartPage() { const p = new URLSearchParams(location.search).get('page'); if (p && /^[a-z-]{2,30}$/.test(p)) { history.replaceState(null, '', '/'); go(p); } }
function boot() { load().then(openStartPage).then(flushQueue).catch((e) => { const v = $('#view'); if (v) v.innerHTML = `<div class="card note-box"><h3>Error cargando la app</h3><p>${esc(e.message)}</p><button class="btn" onclick="location.reload()">Reintentar</button></div>`; }); }
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else setTimeout(boot, 0);
