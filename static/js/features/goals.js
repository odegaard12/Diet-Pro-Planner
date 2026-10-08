/*
 * Diet Pro Planner · "Objetivos": profile & targets, AI status, backups/exports.
 */
(function () {
  'use strict';

  const ACTIVITY = {sedentary: 'Sedentario (oficina)', light: 'Ligero (de pie a ratos)', moderate: 'Moderado (trabajo activo)', active: 'Muy activo (físico)'};
  const MODES = {manual: 'Manual: kcal fijas', auto: 'Automático: fórmula (Mifflin-St Jeor)', adaptive: 'Adaptativo: gasto real medido'};
  const nf = (v, d = 0) => (v === null || v === undefined) ? '—' : Number(v).toLocaleString('es-ES', {maximumFractionDigits: d});

  function field(id, label, value, attrs = '') {
    return `<div class="field span-3"><label for="${id}">${label}</label><input id="${id}" value="${esc(value ?? '')}" ${attrs}></div>`;
  }
  function select(id, label, options, value, span = 3) {
    return `<div class="field span-${span}"><label for="${id}">${label}</label><select id="${id}">${Object.entries(options).map(([k, v]) => `<option value="${esc(k)}" ${k === value ? 'selected' : ''}>${esc(v)}</option>`).join('')}</select></div>`;
  }

  function computedPanel(data) {
    const c = data.computed || {}, t = data.adaptive_tdee || {};
    const usedLabel = {manual: 'manual', auto: 'fórmula', adaptive: 'gasto real medido'}[c.kcal_mode_used] || c.kcal_mode_used;
    const note = c.kcal_mode !== c.kcal_mode_used
      ? `<p class="goals-warn">El modo elegido aún no se puede aplicar (${c.missing_for_auto?.length ? 'faltan: ' + c.missing_for_auto.join(', ') : 'faltan datos para el gasto real'}); se usa "${esc(usedLabel)}".</p>` : '';
    return `<div class="goals-computed">
      <article><span>Objetivo base hoy</span><b>${nf(c.kcal_base_target)} kcal</b><small>modo ${esc(usedLabel)} · + bonus de deporte</small></article>
      <article><span>Proteína</span><b>${nf(c.protein?.goal_min_g)}–${nf(c.protein?.max_g)} g</b><small>objetivo ${nf(c.protein?.target_g)} g</small></article>
      <article><span>Metabolismo basal</span><b>${c.bmr_kcal ? nf(c.bmr_kcal) + ' kcal' : '—'}</b><small>${c.tdee_without_workouts_kcal ? 'sin deporte ≈ ' + nf(c.tdee_without_workouts_kcal) + ' kcal' : 'completa sexo y año de nacimiento'}</small></article>
      <article><span>Gasto real medido</span><b>${t.tdee ? nf(t.tdee) + ' kcal' : 'calibrando'}</b><small>${t.tdee ? `confianza ${esc(t.confidence)} · ${t.logged_days} días` : esc(t.message || '')}</small></article>
      <article><span>Peso actual · IMC</span><b>${nf(c.weight_kg, 1)} kg</b><small>IMC ${nf(c.bmi, 1)} · déficit plan ${nf(c.deficit_kcal)} kcal/día</small></article>
    </div>${note}`;
  }

  function aiPanel(ai) {
    if (!ai) return '';
    const status = ai.enabled
      ? `<span class="pill good">Activa</span> ${esc(ai.provider === 'anthropic' ? 'Claude' : 'Compatible OpenAI')} · <code>${esc(ai.model)}</code> · ${ai.used_today}/${ai.daily_limit} usos hoy`
      : '<span class="pill warn">Desactivada</span> El Coach local por reglas sigue funcionando.';
    return `<article class="card goals-card"><h3>🤖 IA opcional (BYOK)</h3><p>${status}</p>
      <p class="muted">${esc(ai.privacy)}</p>
      ${ai.enabled ? '' : '<p class="muted">Para activarla añade <code>ANTHROPIC_API_KEY</code> a tu <code>.env</code> (o <code>DPP_AI_BASE_URL</code> + <code>DPP_AI_MODEL</code> para Ollama/compatibles) y reinicia. La clave nunca se guarda en la base de datos.</p>'}</article>`;
  }

  function dataPanel(b) {
    const list = (b?.backups || []).slice(0, 6).map((x) => `<li><b>${esc(x.name)}</b><small>${esc(x.created_at)} · ${nf(x.size_kb)} KB</small></li>`).join('');
    return `<article class="card goals-card"><h3>💾 Copias y exportación</h3>
      <p class="muted">Copia automática diaria (se guardan ${nf(b?.keep_daily)}) y antes de cada actualización de esquema. Esquema v${esc(b?.schema_version ?? '?')}.</p>
      <div class="goals-actions"><a class="btn" href="/api/backup/download">Descargar copia (.db)</a><button class="btn secondary" onclick="dppBackupNow(this)">Crear copia ahora</button></div>
      <div class="goals-actions"><a class="btn secondary" href="/api/export/meals.csv">Comidas CSV</a><a class="btn secondary" href="/api/export/weights.csv">Pesos CSV</a><a class="btn secondary" href="/api/export/workouts.csv">Entrenos CSV</a><a class="btn secondary" href="/api/export" target="_blank" rel="noopener">JSON</a></div>
      ${list ? `<ul class="goals-backups">${list}</ul>` : '<p class="muted">Aún no hay copias locales.</p>'}</article>`;
  }

  function view(data, ai, backups) {
    const p = data.profile;
    return `<section class="pg-head"><div><span class="ui5-kicker">Objetivos personales</span><h3>Tus metas mandan sobre todo el análisis</h3><p class="muted">Coach, score, Progreso e IA usan estos valores. Nada sale de tu Raspberry.</p></div></section>
      <article class="card goals-card">${computedPanel(data)}</article>
      <article class="card goals-card"><h3>🎯 Perfil y metas</h3>
        <div class="row">
          ${select('gSex', 'Sexo (para el basal)', {'': '—', male: 'Hombre', female: 'Mujer'}, p.sex)}
          ${field('gBirth', 'Año de nacimiento', p.birth_year, 'type="number" inputmode="numeric" placeholder="1990"')}
          ${field('gHeight', 'Altura cm', p.height_cm, 'type="number" inputmode="decimal"')}
          ${select('gActivity', 'Actividad diaria (sin entrenos)', ACTIVITY, p.activity_level)}
          ${field('gStart', 'Peso inicial kg', p.start_weight_kg, 'type="number" step="0.1" inputmode="decimal"')}
          ${field('gGoal', 'Peso objetivo kg', p.goal_weight_kg, 'type="number" step="0.1" inputmode="decimal"')}
          ${field('gRate', 'Ritmo deseado kg/semana', p.target_rate_kg_week, 'type="number" step="0.05" min="0" max="1.2" inputmode="decimal"')}
          ${select('gMode', 'Cálculo de calorías', MODES, p.kcal_mode)}
          ${field('gKcal', 'Kcal base (modo manual)', p.kcal_base_target, 'type="number" inputmode="numeric"')}
          ${select('gProteinMode', 'Proteína', {fixed: 'Gramos fijos', per_kg: 'Por kg de peso'}, p.protein_mode)}
          ${field('gProtein', 'Proteína objetivo g', p.protein_target_g, 'type="number" inputmode="numeric"')}
          ${field('gProteinKg', 'Proteína g/kg', p.protein_g_per_kg, 'type="number" step="0.1" inputmode="decimal"')}
          ${field('gOilN', 'Aceite normal g', p.oil_normal_g, 'type="number" inputmode="decimal"')}
          ${field('gOilM', 'Aceite máximo g', p.oil_max_g, 'type="number" inputmode="decimal"')}
          ${field('gBonus', 'Bonus deporte (0–1)', p.sport_bonus_factor, 'type="number" step="0.05" min="0" max="1" inputmode="decimal"')}
          ${field('gBonusMax', 'Máx. kcal deporte', p.max_sport_bonus_kcal, 'type="number" inputmode="numeric"')}
        </div>
        <p class="muted">Bonus deporte: fracción de las kcal de entreno que se suman al objetivo del día (los relojes suelen sobrestimar). El modo adaptativo usa tu gasto real cuando hay 14+ días registrados y 6+ pesajes.</p>
        <div class="goals-actions"><button class="btn" onclick="dppSaveGoals(this)">Guardar objetivos</button></div>
      </article>
      <section class="goals-two">${aiPanel(ai)}${dataPanel(backups)}</section>
      <div class="footer-space"></div>`;
  }

  async function renderGoals() {
    $('#view').innerHTML = '<section class="card"><h3>Cargando objetivos…</h3></section>';
    try {
      const [data, ai, backups] = await Promise.all([api('/api/profile'), api('/api/ai/status').catch(() => null), api('/api/backup').catch(() => null)]);
      if (page !== 'goals') return;
      $('#view').innerHTML = view(data, ai, backups);
    } catch (e) {
      $('#view').innerHTML = `<section class="card note-box"><h3>No pude cargar los objetivos</h3><p>${esc(e.message)}</p></section>`;
    }
  }

  window.dppSaveGoals = async (btn) => {
    const val = (id) => $(id)?.value ?? '';
    const payload = {
      sex: val('#gSex'), birth_year: val('#gBirth'), height_cm: val('#gHeight'), activity_level: val('#gActivity'),
      start_weight_kg: val('#gStart'), goal_weight_kg: val('#gGoal'), target_rate_kg_week: val('#gRate'), kcal_mode: val('#gMode'),
      kcal_base_target: val('#gKcal'), protein_mode: val('#gProteinMode'), protein_target_g: val('#gProtein'), protein_g_per_kg: val('#gProteinKg'),
      oil_normal_g: val('#gOilN'), oil_max_g: val('#gOilM'), oil_bad_g: Math.max(Number(val('#gOilM')) + 5, Number(window.DPP_PROFILE?.profile?.oil_bad_g || 15)), sport_bonus_factor: val('#gBonus'), max_sport_bonus_kcal: val('#gBonusMax'),
    };
    await busy(btn, async () => {
      const r = await api('/api/profile', {method: 'PUT', body: JSON.stringify(payload)});
      toast(r.message || 'Objetivos guardados');
      await window.DPP.loadProfile();
      renderGoals();
    });
  };
  window.dppBackupNow = async (btn) => { await busy(btn, async () => { const r = await api('/api/backup', {method: 'POST'}); toast(`${r.message}: ${r.name}`); renderGoals(); }); };

  window.DPP.registerPage({id: 'goals', icon: '🎯', label: 'Objetivos', sub: 'Metas y datos', title: 'Objetivos y datos', render: renderGoals});
})();
