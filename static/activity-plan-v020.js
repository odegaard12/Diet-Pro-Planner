/* Diet Pro Planner v0.0.20 · planned vs real activity */
(function () {
  'use strict';

  const VERSION = 'v0.0.20-dev';
  let weekStart = mondayOf(new Date());
  let activityData = null;
  let editingId = null;

  const esc = (value) => String(value ?? '')
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');

  function isoDate(value) {
    const d = value instanceof Date ? new Date(value) : new Date(`${value}T12:00:00`);
    return d.toISOString().slice(0, 10);
  }

  function mondayOf(value) {
    const d = value instanceof Date ? new Date(value) : new Date(`${value}T12:00:00`);
    const day = (d.getDay() + 6) % 7;
    d.setDate(d.getDate() - day);
    d.setHours(12, 0, 0, 0);
    return d;
  }

  function addDays(value, days) {
    const d = new Date(value);
    d.setDate(d.getDate() + days);
    return d;
  }

  function formatDay(value) {
    return new Intl.DateTimeFormat('es-ES', {weekday: 'short', day: 'numeric', month: 'short'}).format(value);
  }

  function sportIcon(value) {
    const text = String(value || '').toLowerCase();
    if (/padel|pádel/.test(text)) return '🎾';
    if (/run|carrera|cinta/.test(text)) return '🏃';
    if (/walk|paseo|camin|hike/.test(text)) return '🚶';
    if (/ride|bike|bici/.test(text)) return '🚴';
    if (/weight|fuerza|pesas|gimnasio|tren/.test(text)) return '🏋️';
    if (/hiit|funcional|workout/.test(text)) return '⚡';
    if (/movilidad|mobility|core/.test(text)) return '🧘';
    if (/swim|nataci/.test(text)) return '🏊';
    return '🏅';
  }

  function statusMeta(status) {
    return {
      completed: ['Cumplida', 'good'],
      changed: ['Cambiada', 'info'],
      missed: ['No realizada', 'bad'],
      pending: ['Pendiente hoy', 'warn'],
      upcoming: ['Próxima', 'neutral'],
      skipped: ['Omitida', 'muted'],
      cancelled: ['Cancelada', 'muted']
    }[status] || [status || 'Pendiente', 'neutral'];
  }

  function request(path, options) {
    return api(path, options || {});
  }

  function weekRange() {
    return {from: isoDate(weekStart), to: isoDate(addDays(weekStart, 6))};
  }

  function syncVersion() {
    document.title = `Diet Pro Planner · ${VERSION}`;
    const eyebrow = document.querySelector('.eyebrow');
    if (eyebrow) eyebrow.textContent = `Dieta controlada · ${VERSION}`;
    const badge = document.querySelector('#ui5Badge');
    if (badge) badge.textContent = VERSION;
  }

  function planCard(plan) {
    const [label, tone] = statusMeta(plan.status);
    const actual = plan.matched_workout;
    const editable = !['completed', 'changed'].includes(plan.status);
    return `
      <article class="activity-plan-card ${tone}">
        <div class="activity-plan-card-head">
          <span class="activity-plan-icon">${sportIcon(plan.sport_type || plan.title)}</span>
          <div class="activity-plan-title">
            <b>${esc(plan.title)}</b>
            <small>${esc(plan.time || 'Sin hora')} · ${esc(plan.sport_type || 'Entreno')} · ${fmt(plan.minutes || 0)} min</small>
          </div>
          <span class="activity-status ${tone}">${label}</span>
        </div>
        <div class="activity-plan-meta">
          ${Number(plan.distance_km || 0) ? `<span>${fmt(plan.distance_km)} km</span>` : ''}
          ${Number(plan.target_kcal || 0) ? `<span>${fmt(plan.target_kcal)} kcal objetivo</span>` : ''}
          <span>${esc(({easy:'Suave',moderate:'Moderada',hard:'Alta',recovery:'Recuperación'})[plan.intensity] || 'Moderada')}</span>
        </div>
        ${plan.notes ? `<p>${esc(plan.notes)}</p>` : ''}
        ${actual ? `
          <div class="activity-real-match">
            <span>REAL</span>
            <div><b>${esc(actual.name || 'Actividad')}</b><small>${esc(actual.time || '')} · ${fmt(actual.minutes || 0)} min · ${fmt(actual.kcal || 0)} kcal${Number(actual.distance_km || 0) ? ` · ${fmt(actual.distance_km)} km` : ''}</small></div>
          </div>` : ''}
        <div class="activity-plan-actions">
          <button class="btn secondary small" onclick="activityPlanEdit(${Number(plan.id)})">Editar</button>
          ${editable && plan.manual_status !== 'skipped' ? `<button class="btn secondary small" onclick="activityPlanSetStatus(${Number(plan.id)},'skipped')">Omitir</button>` : ''}
          ${plan.manual_status === 'skipped' || plan.manual_status === 'cancelled' ? `<button class="btn secondary small" onclick="activityPlanSetStatus(${Number(plan.id)},'planned')">Reactivar</button>` : ''}
          <button class="btn small danger" onclick="activityPlanDelete(${Number(plan.id)})">Eliminar</button>
        </div>
      </article>`;
  }

  function extraCard(workout) {
    return `
      <article class="activity-extra-card">
        <span class="activity-plan-icon">${sportIcon(workout.name)}</span>
        <div><b>${esc(workout.name || 'Actividad real')}</b><small>${esc(workout.time || '')} · ${fmt(workout.minutes || 0)} min · ${fmt(workout.kcal || 0)} kcal</small></div>
        <span>Extra real</span>
      </article>`;
  }

  function renderWeek() {
    const root = document.querySelector('#activityWeek');
    if (!root || !activityData) return;
    const plans = activityData.plans || [];
    const extras = activityData.extra_workouts || [];
    root.innerHTML = Array.from({length: 7}, (_, index) => {
      const dayDate = addDays(weekStart, index);
      const iso = isoDate(dayDate);
      const dayPlans = plans.filter((item) => item.date === iso);
      const dayExtras = extras.filter((item) => item.date === iso);
      const todayClass = iso === new Date().toISOString().slice(0, 10) ? 'today' : '';
      return `
        <section class="activity-day ${todayClass}">
          <header><div><span>${formatDay(dayDate)}</span>${todayClass ? '<b>HOY</b>' : ''}</div><button onclick="activityPlanNewForDate('${iso}')">+</button></header>
          <div class="activity-day-body">
            ${dayPlans.map(planCard).join('')}
            ${dayExtras.map(extraCard).join('')}
            ${!dayPlans.length && !dayExtras.length ? '<div class="activity-day-empty">Sin actividad</div>' : ''}
          </div>
        </section>`;
    }).join('');
  }

  function renderSummary() {
    const summary = activityData?.summary || {};
    const adherence = summary.adherence_pct;
    const root = document.querySelector('#activitySummary');
    if (!root) return;
    root.innerHTML = `
      <div class="activity-summary-main">
        <span>Cumplimiento</span>
        <b>${adherence === null || adherence === undefined ? '—' : `${adherence}%`}</b>
        <small>${summary.fulfilled || 0} de ${summary.eligible || 0} planes evaluables</small>
      </div>
      <div><span>Planificados</span><b>${summary.planned || 0}</b><small>${fmt(summary.planned_minutes || 0)} min</small></div>
      <div><span>Realizados</span><b>${(summary.completed || 0) + (summary.changed || 0)}</b><small>${fmt(summary.real_minutes || 0)} min</small></div>
      <div><span>No realizados</span><b>${summary.missed || 0}</b><small>${summary.skipped || 0} omitidos</small></div>
      <div><span>Gasto real</span><b>${fmt(summary.real_kcal || 0)}</b><small>kcal registradas</small></div>`;
  }

  function renderActivityPlanPage() {
    document.body.classList.remove('dpp-strava-page', 'dpp-pantry-page');
    document.body.classList.add('dpp-activity-plan-page');
    setTitle('Plan de actividad');
    const range = weekRange();
    document.querySelector('#view').innerHTML = `
      <section class="activity-plan-hero">
        <div>
          <span class="activity-kicker">PLANIFICADO VS. REAL · ${VERSION}</span>
          <h2>Tu semana de actividad</h2>
          <p>Planifica lo importante y deja que Strava o el registro manual confirmen lo que realmente hiciste.</p>
        </div>
        <div class="activity-week-nav">
          <button class="btn secondary" onclick="activityPlanMoveWeek(-1)">←</button>
          <button class="btn secondary" onclick="activityPlanToday()">Esta semana</button>
          <button class="btn secondary" onclick="activityPlanMoveWeek(1)">→</button>
        </div>
      </section>

      <section id="activitySummary" class="activity-summary-grid">
        <div class="activity-loading">Calculando semana…</div>
      </section>

      <section class="activity-plan-layout">
        <div class="card activity-plan-calendar">
          <header class="activity-section-head">
            <div><span>SEMANA</span><h3>${range.from} → ${range.to}</h3></div>
            <button class="btn" onclick="activityPlanNewForDate('${new Date().toISOString().slice(0, 10)}')">+ Planificar actividad</button>
          </header>
          <div id="activityWeek" class="activity-week-grid"><div class="activity-loading">Cargando planes y entrenos reales…</div></div>
        </div>

        <aside class="card activity-plan-form-card">
          <header><span>PLANIFICAR</span><h3 id="activityFormTitle">Nueva actividad</h3><p>Después se emparejará automáticamente con Strava o con un entreno manual del mismo día.</p></header>
          <div class="activity-plan-form">
            <label><span>Fecha</span><input id="apDate" type="date" value="${new Date().toISOString().slice(0, 10)}"></label>
            <label><span>Hora</span><input id="apTime" type="time" value="19:00"></label>
            <label class="wide"><span>Actividad</span><select id="apSport" onchange="activityPlanSportChanged()">
              <option>Pádel</option><option>Carrera</option><option>Fuerza</option><option>Funcional</option>
              <option>Movilidad + Core</option><option>Bici</option><option>Caminata</option><option>Otro</option>
            </select></label>
            <label class="wide"><span>Título</span><input id="apTitle" value="Pádel" placeholder="Ej. Pádel por la tarde"></label>
            <label><span>Minutos</span><input id="apMinutes" type="number" min="0" value="90"></label>
            <label><span>Distancia km</span><input id="apDistance" type="number" min="0" step="0.1"></label>
            <label><span>Kcal objetivo</span><input id="apKcal" type="number" min="0" placeholder="opcional"></label>
            <label><span>Intensidad</span><select id="apIntensity"><option value="easy">Suave</option><option value="moderate" selected>Moderada</option><option value="hard">Alta</option><option value="recovery">Recuperación</option></select></label>
            <label class="wide"><span>Notas</span><textarea id="apNotes" placeholder="Objetivo, sensaciones previstas, contexto…"></textarea></label>
          </div>
          <div class="activity-form-actions">
            <button class="btn" onclick="activityPlanSave()">Guardar plan</button>
            <button class="btn secondary" onclick="activityPlanResetForm()">Limpiar</button>
          </div>
        </aside>
      </section>`;
    loadActivityPlan();
    syncVersion();
  }

  async function loadActivityPlan() {
    const range = weekRange();
    try {
      activityData = await request(`/api/activity-plan?from=${encodeURIComponent(range.from)}&to=${encodeURIComponent(range.to)}`);
      renderSummary();
      renderWeek();
    } catch (error) {
      const root = document.querySelector('#activityWeek');
      if (root) root.innerHTML = `<div class="activity-error"><b>No se pudo cargar la planificación</b><span>${esc(error.message)}</span></div>`;
    }
  }

  window.activityPlanMoveWeek = function (direction) {
    weekStart = addDays(weekStart, Number(direction || 0) * 7);
    renderActivityPlanPage();
  };

  window.activityPlanToday = function () {
    weekStart = mondayOf(new Date());
    renderActivityPlanPage();
  };

  window.activityPlanSportChanged = function () {
    const sport = document.querySelector('#apSport')?.value || '';
    const title = document.querySelector('#apTitle');
    if (title && (!title.value.trim() || ['Pádel','Carrera','Fuerza','Funcional','Movilidad + Core','Bici','Caminata','Otro'].includes(title.value.trim()))) {
      title.value = sport === 'Otro' ? '' : sport;
    }
    const minutes = document.querySelector('#apMinutes');
    if (minutes && !minutes.dataset.touched) {
      const defaults = {'Pádel':90,'Carrera':45,'Fuerza':60,'Funcional':50,'Movilidad + Core':35,'Bici':90,'Caminata':45};
      minutes.value = defaults[sport] || 45;
    }
  };

  window.activityPlanNewForDate = function (value) {
    activityPlanResetForm();
    const input = document.querySelector('#apDate');
    if (input) input.value = value;
    document.querySelector('.activity-plan-form-card')?.scrollIntoView({behavior:'smooth', block:'start'});
  };

  window.activityPlanResetForm = function () {
    editingId = null;
    const title = document.querySelector('#activityFormTitle');
    if (title) title.textContent = 'Nueva actividad';
    const sport = document.querySelector('#apSport');
    if (sport) sport.value = 'Pádel';
    const values = {
      apDate: new Date().toISOString().slice(0, 10), apTime: '19:00', apTitle: 'Pádel',
      apMinutes: '90', apDistance: '', apKcal: '', apIntensity: 'moderate', apNotes: ''
    };
    Object.entries(values).forEach(([id, value]) => {
      const node = document.querySelector(`#${id}`);
      if (node) node.value = value;
    });
  };

  window.activityPlanEdit = function (id) {
    const plan = (activityData?.plans || []).find((item) => Number(item.id) === Number(id));
    if (!plan) return;
    editingId = Number(id);
    document.querySelector('#activityFormTitle').textContent = 'Editar actividad';
    document.querySelector('#apDate').value = plan.date;
    document.querySelector('#apTime').value = plan.time || '';
    document.querySelector('#apSport').value = [...document.querySelector('#apSport').options].some((option) => option.value === plan.sport_type) ? plan.sport_type : 'Otro';
    document.querySelector('#apTitle').value = plan.title || '';
    document.querySelector('#apMinutes').value = plan.minutes || '';
    document.querySelector('#apDistance').value = plan.distance_km || '';
    document.querySelector('#apKcal').value = plan.target_kcal || '';
    document.querySelector('#apIntensity').value = plan.intensity || 'moderate';
    document.querySelector('#apNotes').value = plan.notes || '';
    document.querySelector('.activity-plan-form-card')?.scrollIntoView({behavior:'smooth', block:'start'});
  };

  window.activityPlanSave = async function () {
    const payload = {
      date: document.querySelector('#apDate').value,
      time: document.querySelector('#apTime').value,
      sport_type: document.querySelector('#apSport').value === 'Otro' ? document.querySelector('#apTitle').value : document.querySelector('#apSport').value,
      title: document.querySelector('#apTitle').value,
      minutes: document.querySelector('#apMinutes').value,
      distance_km: document.querySelector('#apDistance').value,
      target_kcal: document.querySelector('#apKcal').value,
      intensity: document.querySelector('#apIntensity').value,
      notes: document.querySelector('#apNotes').value
    };
    try {
      const path = editingId ? `/api/activity-plan/${editingId}` : '/api/activity-plan';
      const method = editingId ? 'PUT' : 'POST';
      const result = await request(path, {method, body: JSON.stringify(payload)});
      toast(result.message || 'Actividad planificada guardada');
      activityPlanResetForm();
      await loadActivityPlan();
    } catch (error) {
      toast(`Plan de actividad: ${error.message}`);
    }
  };

  window.activityPlanSetStatus = async function (id, status) {
    try {
      const result = await request(`/api/activity-plan/${id}/status`, {method:'POST', body:JSON.stringify({status})});
      toast(result.message || 'Estado actualizado');
      await loadActivityPlan();
    } catch (error) {
      toast(`Plan de actividad: ${error.message}`);
    }
  };

  window.activityPlanDelete = async function (id) {
    if (!confirm('¿Eliminar esta actividad planificada?')) return;
    try {
      const result = await request(`/api/activity-plan/${id}`, {method:'DELETE'});
      toast(result.message || 'Actividad eliminada');
      if (editingId === Number(id)) activityPlanResetForm();
      await loadActivityPlan();
    } catch (error) {
      toast(`Plan de actividad: ${error.message}`);
    }
  };

  if (typeof PAGES !== 'undefined' && !PAGES.some((entry) => entry[0] === 'activity-plan')) {
    const sportIndex = PAGES.findIndex((entry) => entry[0] === 'sport');
    PAGES.splice(sportIndex >= 0 ? sportIndex + 1 : PAGES.length, 0, ['activity-plan', '🗓️', 'Plan deporte']);
  }
  if (typeof UI5_NAV !== 'undefined') UI5_NAV['activity-plan'] = ['🗓️', 'Plan deporte', 'Plan vs real'];

  try {
    const oldRender = render;
    const wrappedRender = function () {
      document.body.classList.toggle('dpp-activity-plan-page', page === 'activity-plan');
      if (page === 'activity-plan') return renderActivityPlanPage();
      return oldRender.apply(this, arguments);
    };
    window.render = wrappedRender;
    render = wrappedRender;
  } catch (error) {
    console.warn('Activity plan v0.0.20 render wrapper', error);
  }

  try { renderNav(); } catch (error) {}
  const observer = new MutationObserver(syncVersion);
  observer.observe(document.documentElement, {childList:true, characterData:true, subtree:true});
  syncVersion();
  setInterval(syncVersion, 700);
})();
