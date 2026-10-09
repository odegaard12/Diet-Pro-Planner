/*
 * Diet Pro Planner · optional AI coach card (home) and AI label reading (foods).
 * Hidden entirely unless the server reports AI as configured (BYOK).
 */
(function () {
  'use strict';

  let status = null;

  async function getStatus() {
    if (status) return status;
    try { status = await api('/api/ai/status'); } catch (e) { status = {enabled: false}; }
    return status;
  }

  function adviceHtml(r) {
    const a = r.advice || {}, meal = a.next_meal || {};
    const items = (meal.items || []).map((i) => `<li><b>${esc(i.food)}</b> · ${fmt(i.grams)} g</li>`).join('');
    const tips = (a.tips || []).slice(0, 4).map((t) => `<li>${esc(t)}</li>`).join('');
    const warns = (a.warnings || []).map((w) => `<p class="ai-warn">⚠️ ${esc(w)}</p>`).join('');
    return `<div class="ai-body">
      <h4>${esc(a.headline || 'Análisis del día')}</h4><p>${esc(a.assessment || '')}</p>${warns}
      <div class="ai-grid"><div><span class="ai-label">Siguiente comida · ${esc(meal.title || '')}</span><ul>${items}</ul><small>${esc(meal.why || '')}</small></div>
      <div><span class="ai-label">Consejos</span><ul>${tips}</ul></div></div>
      <small class="muted">${r.cached ? 'Respuesta en caché · ' : ''}${esc(r.provider === 'anthropic' ? 'Claude' : 'IA')} ${esc(r.model || '')} · orientativo, no es consejo médico.</small>
    </div>`;
  }

  async function ask(date, btn) {
    const box = document.querySelector('#aiCoachBody');
    const question = String(document.querySelector('#aiQuestion')?.value || '').trim();
    await busy(btn, async () => {
      if (box) box.innerHTML = '<p class="muted">Pensando con tus datos de hoy…</p>';
      try {
        const r = await api('/api/ai/coach', {method: 'POST', body: JSON.stringify({date, question})});
        if (box) box.innerHTML = adviceHtml(r);
        status = null;
      } catch (e) {
        if (box) box.innerHTML = `<p class="ai-warn">${esc(e.message)}</p>`;
      }
    });
  }

  async function mountHome(selector, date) {
    const host = document.querySelector(selector);
    if (!host) return;
    const s = await getStatus();
    if (!s.enabled || !document.body.contains(host)) return;
    host.innerHTML = `<section class="card ai-card"><header><div><span class="ui5-kicker">Coach IA · ${esc(s.provider === 'anthropic' ? 'Claude' : 'IA local')}</span><h3>Pregunta sobre tu día</h3></div><small class="muted">${s.used_today}/${s.daily_limit} hoy</small></header>
      <div class="ai-ask"><input id="aiQuestion" maxlength="500" placeholder="Opcional: ¿qué ceno si mañana tengo pádel?" onkeydown="if(event.key==='Enter'){event.preventDefault();this.nextElementSibling.click()}"><button class="btn" type="button">Analizar</button></div>
      <div id="aiCoachBody"><p class="muted">Envía tus objetivos, lo comido hoy y la despensa para un análisis personalizado.</p></div></section>`;
    host.querySelector('.ai-ask .btn').onclick = (ev) => ask(date, ev.currentTarget);
  }

  async function offerLabel(selector, photoPath, confidence) {
    const host = document.querySelector(selector);
    if (!host || !photoPath) return;
    const s = await getStatus();
    if (!s.enabled) return;
    host.innerHTML = `<button class="btn small ${confidence === 'alta' ? 'secondary' : ''}" type="button">✨ Leer con IA</button>`;
    host.querySelector('button').onclick = async (ev) => {
      await busy(ev.currentTarget, async () => {
        toast('Leyendo la etiqueta con IA…');
        const r = await api('/api/ai/label', {method: 'POST', body: JSON.stringify({photo_path: photoPath})});
        applyLabelResult(r);
        toast('Etiqueta leída con IA: revisa y guarda');
      });
    };
  }

  window.DPPAICoach = {mountHome, offerLabel};
})();
