/* "Revisión de datos" card in Ajustes (v0.6.0): read-only check of typos and broken references. */
(function () {
  'use strict';

  const ICON = {error: '⛔', warn: '⚠️', info: 'ℹ️'};
  const LABEL = {error: 'Error', warn: 'Revisar', info: 'Aviso'};
  const FIX = {foods: 'Alimentos', history: 'Historial', weights: 'Peso', sport: 'Entrenos', templates: 'Plantillas', goals: 'Ajustes'};

  window.dppAuditCardHtml = () => `<article class="card goals-card" id="dataAudit"><h3>Revisión de datos</h3>
    <p class="muted">Busca erratas probables (pesos o raciones disparatados, plantillas rotas, copias antiguas). Solo lee: no cambia nada.</p>
    <div class="goals-actions"><button class="btn secondary" type="button" onclick="dppRunAudit(this)">Revisar ahora</button></div>
    <div id="dataAuditResult" aria-live="polite"></div></article>`;

  function findingHtml(f) {
    const items = f.items.length ? `<ul>${f.items.map((i) => `<li>${esc(i)}</li>`).join('')}</ul>` : '';
    const more = f.count > f.items.length ? `<small class="muted">y ${f.count - f.items.length} más</small>` : '';
    return `<section class="audit-finding ${esc(f.level)}"><header><span aria-hidden="true">${ICON[f.level] || ''}</span>
      <b>${esc(f.title)}</b><span class="pill">${esc(LABEL[f.level] || f.level)}${f.count ? ` · ${Number(f.count)}` : ''}</span></header>
      <p class="muted">${esc(f.detail)}</p>${items}${more}
      <button class="btn small secondary" type="button" onclick="go('${esc(f.fix)}')">Ir a ${esc(FIX[f.fix] || 'la sección')}</button></section>`;
  }

  window.dppRunAudit = async (btn) => {
    await busy(btn, async () => {
      const r = await api('/api/data-audit');
      const box = document.querySelector('#dataAuditResult');
      if (!box) return;
      box.innerHTML = r.findings.length
        ? `<p><b>${r.findings.length}</b> cosa${r.findings.length > 1 ? 's' : ''} que mirar.</p>${r.findings.map(findingHtml).join('')}`
        : '<div class="empty">Todo en orden: no he encontrado nada raro en tus datos.</div>';
    });
  };
})();
