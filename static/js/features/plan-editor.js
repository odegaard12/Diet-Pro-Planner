/*
 * Diet Pro Planner · weekly meal plan editor ("Plan").
 * Moved out of app.js; behaviour unchanged (stored through POST /api/plans).
 */
(function () {
  'use strict';

  const STATUSES = ['planificado', 'pendiente ajustar', 'borrador', 'realizado'];

  function defaultWeek() {
    return {
      name: 'Semana dieta controlada · editable',
      notes: 'Plan local editable. Proteína en objetivo, aceite medido, pasta/arroz en seco. Ajustar según deporte y hambre real.',
      days: [
        {day: 'Lunes', breakfast: 'Tostada 42 g + café con edulcorante + yogur proteico 120 g.', lunch: '80 g pasta seca + pollo 200 g crudo + verdura. Aceite 5 g.', snack: 'Fruta o yogur proteico.', dinner: '2 huevos + jamón cocido 80 g + verdura 250 g.', target: 'proteína en objetivo · aceite 5–10 g', status: 'planificado'},
        {day: 'Martes', breakfast: 'Tostada + café + yogur proteico.', lunch: 'Tupper: arroz pesado en seco + pollo/atún + verdura + 5 g aceite.', snack: 'Queso fresco batido.', dinner: 'Pescado + verdura.', target: 'rutina', status: 'borrador'},
        {day: 'Miércoles', breakfast: 'Desayuno base.', lunch: 'Proteína principal + verdura + hidrato si hay actividad.', snack: 'Fruta + yogur proteico.', dinner: 'Proteína + verdura. Evitar dulce nocturno.', target: 'déficit controlado', status: 'borrador'},
      ],
    };
  }

  function normalize(p) {
    p = p || {};
    const days = Array.isArray(p.days) ? p.days : [];
    return {
      name: p.name || 'Plan semanal',
      notes: p.notes || '',
      days: days.map((d) => ({day: d.day || '', breakfast: d.breakfast || '', lunch: d.lunch || '', snack: d.snack || '', dinner: d.dinner || '', target: d.target || '', status: d.status || 'borrador'})),
    };
  }

  function currentPlan() {
    const row = state.plans && state.plans.length ? state.plans[0] : null;
    try { return normalize(row ? JSON.parse(row.payload) : defaultWeek()); } catch (e) { return normalize(defaultWeek()); }
  }

  function stats(p) {
    const planned = p.days.filter((d) => [d.breakfast, d.lunch, d.snack, d.dinner].some((x) => String(x || '').trim())).length;
    return {days: p.days.length, planned, missing: Math.max(0, 7 - p.days.length)};
  }

  function dayHtml(d, idx) {
    const status = d.status || 'borrador';
    const area = (field, label, ph) => `<label><b>${label}</b><textarea data-plan-field="${field}" placeholder="${ph}">${esc(d[field])}</textarea></label>`;
    return `<article class="ui5-edit-day" data-plan-day="${idx}">
      <header><span>${idx + 1}</span><div>
        <input class="ui5-day-title" data-plan-field="day" value="${esc(d.day)}" placeholder="Ej. Viernes · recuperación">
        <select data-plan-field="status">${STATUSES.map((x) => `<option value="${esc(x)}" ${x === status ? 'selected' : ''}>${esc(x)}</option>`).join('')}</select>
      </div><button class="btn small danger" onclick="ui5DeletePlanDay(${idx})" aria-label="Borrar día">×</button></header>
      ${area('breakfast', 'Desayuno', 'Tostada + yogur...')}${area('lunch', 'Comida', 'Tupper, pasta/arroz, proteína...')}${area('snack', 'Merienda', 'Fruta, yogur, pre-entreno...')}${area('dinner', 'Cena', 'Proteína + verdura...')}
      <label><b>Objetivo</b><input data-plan-field="target" value="${esc(d.target)}" placeholder="proteína / aceite 5 g"></label>
    </article>`;
  }

  function readDom() {
    const p = {name: $('#planName')?.value || 'Plan semanal', notes: $('#planNotes')?.value || '', days: []};
    document.querySelectorAll('[data-plan-day]').forEach((card) => {
      const d = {};
      card.querySelectorAll('[data-plan-field]').forEach((el) => { d[el.dataset.planField] = el.value || ''; });
      p.days.push(d);
    });
    return normalize(p);
  }

  function refreshStats(p) {
    const st = stats(p || readDom());
    const el = $('#ui5PlanStats');
    if (el) el.innerHTML = `<span><b>${st.days}</b><small>días</small></span><span><b>${st.planned}</b><small>con comidas</small></span><span><b>${st.missing}</b><small>faltan</small></span>`;
  }

  function renderBoard(p) {
    const board = $('#ui5PlanBoard'); if (!board) return;
    board.innerHTML = p.days.map(dayHtml).join('');
    refreshStats(p);
  }

  window.ui5RefreshPlanStats = () => refreshStats();
  window.ui5AddPlanDay = () => { const p = readDom(); p.days.push({day: 'Nuevo día', breakfast: '', lunch: '', snack: '', dinner: '', target: '', status: 'borrador'}); renderBoard(p); };
  window.ui5DeletePlanDay = (idx) => { const p = readDom(); p.days.splice(idx, 1); renderBoard(p); };
  window.ui5CompletePlanWeek = () => {
    const p = readDom();
    while (p.days.length < 7) p.days.push({day: `Día ${p.days.length + 1}`, breakfast: 'Desayuno base: tostada + café + yogur proteico.', lunch: 'Proteína + carbo pesado en seco si toca + verdura.', snack: 'Fruta o yogur proteico.', dinner: 'Proteína + verdura. Aceite medido.', target: 'ajustar según actividad', status: 'borrador'});
    renderBoard(p); toast('Semana completada en borrador');
  };
  window.ui5ApplyDefaultPlan = () => { const p = normalize(defaultWeek()); $('#planName').value = p.name; $('#planNotes').value = p.notes; renderBoard(p); toast('Plan base cargado'); };
  window.ui5SaveEditablePlan = async (btn) => {
    await busy(btn, async () => { await api('/api/plans', {method: 'POST', body: JSON.stringify({payload: readDom()})}); toast('Plan guardado'); await load(); go('plan'); });
  };
  window.ui5ExportPlanJson = () => {
    const raw = JSON.stringify(readDom(), null, 2);
    const box = $('#planRaw'); if (box) box.value = raw;
    navigator.clipboard?.writeText(raw).then(() => toast('JSON copiado')).catch(() => toast('JSON listo abajo'));
  };
  window.savePlan = async (btn) => {
    await busy(btn, async () => { await api('/api/plans', {method: 'POST', body: JSON.stringify({raw: $('#planRaw').value})}); toast('Plan importado'); await load(); go('plan'); });
  };

  window.renderPlan = function () {
    const p = currentPlan(); const st = stats(p);
    $('#view').innerHTML = `
      <section class="ui5-plan-hero2"><div><span class="ui5-kicker">Plan semanal previsto</span><h3>Plan previsto editable. El real registrado se consulta en Historial.</h3><p>Si el plan anterior venía roto, pulsa “Cargar plan base” o “Completar semana”.</p></div>
        <div id="ui5PlanStats" class="ui5-plan-stats"><span><b>${st.days}</b><small>días</small></span><span><b>${st.planned}</b><small>con comidas</small></span><span><b>${st.missing}</b><small>faltan</small></span></div></section>
      <section class="card ui5-plan-toolbar">
        <div class="row compact-row"><div class="field span-5"><label>Nombre del plan</label><input id="planName" value="${esc(p.name)}" oninput="ui5RefreshPlanStats()"></div><div class="field span-7"><label>Notas</label><input id="planNotes" value="${esc(p.notes)}" oninput="ui5RefreshPlanStats()"></div></div>
        <div class="ui5-plan-actions"><button class="btn" onclick="ui5SaveEditablePlan(this)">Guardar cambios</button><button class="btn secondary" onclick="ui5AddPlanDay()">Añadir día</button><button class="btn secondary" onclick="ui5CompletePlanWeek()">Completar semana</button><button class="btn secondary" onclick="ui5ApplyDefaultPlan()">Cargar plan base</button><button class="btn secondary" onclick="ui5ExportPlanJson()">Copiar/mostrar JSON</button></div>
      </section>
      <section id="ui5PlanBoard" class="ui5-edit-plan-board">${p.days.map(dayHtml).join('')}</section>
      <section class="card ui5-plan-json"><h3>JSON del plan</h3><p class="muted">Para importar otro plan: pega JSON y pulsa importar.</p><textarea id="planRaw" placeholder='{"name":"Semana...","days":[...]}'></textarea><button class="btn secondary" onclick="savePlan(this)">Importar JSON pegado</button></section>`;
  };
})();
