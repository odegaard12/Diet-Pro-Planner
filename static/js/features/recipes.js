/* Plantillas y recetas (v0.7.0): search + filters + compact rows; tapping a row opens the usual card to change grams. */
(function () {
  'use strict';

  const CATS = [['all', 'Todas'], ['mine', 'Mis plantillas'], ['desayuno', 'Desayuno'], ['comida', 'Comida'], ['cena', 'Cena'], ['merienda', 'Merienda'], ['postre', 'Postre'], ['deporte', 'Deporte']];
  const LABEL = Object.fromEntries(CATS);
  let cat = 'all';
  let open = null;

  const meta = (t) => { try { const p = JSON.parse(t.payload || '{}'); return {recipe: !!p.recipe, category: p.recipe ? (p.category || 'comida') : 'mine'}; } catch (e) { return {recipe: false, category: 'mine'}; } };

  function totals(t) {
    const items = templateItems(t);
    const sum = calcList(items);
    return {n: items.length, kcal: sum.kcal, protein: sum.protein};
  }

  function row(t) {
    const m = meta(t); const s = totals(t); const isOpen = open === Number(t.id);
    return `<div class="food-row tpl-row" role="button" tabindex="0" aria-expanded="${isOpen}" onclick="dppToggleTpl(${Number(t.id)})" onkeydown="if(event.target===this&&(event.key==='Enter'||event.key===' ')){event.preventDefault();dppToggleTpl(${Number(t.id)})}">
        <div><b>${esc(t.name)}</b><small>${esc(LABEL[m.category] || m.category)} · ${s.n} ingrediente${s.n === 1 ? '' : 's'}</small></div>
        <span class="food-kcal">${Math.round(s.kcal)}<small>kcal</small></span><span class="food-prot">${Math.round(s.protein)} g<small>prot</small></span></div>
      ${isOpen ? `<div class="tpl-open">${templateCard(t)}</div>` : ''}`;
  }

  function renderList() {
    const box = document.querySelector('#tplList');
    if (!box) return;
    const q = normText(document.querySelector('#tplFilter')?.value);
    const list = state.templates.filter((t) => {
      if (cat !== 'all' && meta(t).category !== cat) return false;
      return !q || normText(t.name).includes(q) || normText(t.notes).includes(q);
    });
    box.innerHTML = (list.slice(0, listLimit('tpls')).map(row).join('') || '<div class="empty">Nada con ese filtro. Guarda tus comidas habituales desde Registrar con «Guardar como plantilla».</div>') + moreButton('tpls', list.length);
  }

  window.dppToggleTpl = (id) => { open = open === Number(id) ? null : Number(id); renderList(); };
  window.dppTplCat = (c) => { cat = c; open = null; renderTemplates(); };
  window.dppTplFilter = () => { open = null; renderList(); };

  window.renderTemplates = function () {
    const recipes = state.templates.filter((t) => meta(t).recipe).length;
    $('#view').innerHTML = `<div class="food-search"><input id="tplFilter" type="search" placeholder="Buscar receta: pollo, avena, tortilla…" aria-label="Buscar plantilla o receta" oninput="dppTplFilter()"></div>
      <div class="chips food-kinds" role="group" aria-label="Tipo">${CATS.map(([k, l]) => `<button type="button" class="chip${cat === k ? ' active' : ''}" aria-pressed="${cat === k}" onclick="dppTplCat('${k}')">${l}</button>`).join('')}</div>
      <p class="muted page-hint">${state.templates.length} plantillas (${recipes} recetas). Toca una para cambiar los gramos y guardarla en dos toques.</p>
      <div id="tplList" class="food-rows"></div>`;
    renderList();
  };

  /* Registrar: the template picker groups my templates and the recipes by type. */
  window.templateOptions = function () {
    const groups = new Map(CATS.slice(1).map(([k, l]) => [k, {label: l, items: []}]));
    state.templates.forEach((t) => groups.get(meta(t).category)?.items.push(t));
    return [...groups.values()].filter((g) => g.items.length).map((g) =>
      `<optgroup label="${esc(g.label)}">${g.items.map((t) => `<option value="${Number(t.id)}">${esc(t.name)}</option>`).join('')}</optgroup>`).join('');
  };
})();
