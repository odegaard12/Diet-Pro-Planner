/* Diet Pro Planner v0.0.19 · editable pantry + coach actions */
(function () {
  'use strict';

  const ENDPOINT = '/api/pantry/v2';
  const COMMON = [
    ['Pollo', 'protein', 'prefer'],
    ['Atún', 'protein', 'prefer'],
    ['Huevos', 'protein', 'prefer'],
    ['Jamón cocido', 'protein', 'normal'],
    ['Queso light', 'dairy', 'normal'],
    ['Yogur proteico', 'dairy', 'prefer'],
    ['Alpro Protein cacao', 'protein_drink', 'normal'],
    ['Judías verdes', 'vegetable', 'prefer'],
    ['Brócoli', 'vegetable', 'normal'],
    ['Arroz', 'carb', 'normal'],
    ['Pasta', 'carb', 'normal'],
    ['Patata', 'carb', 'normal'],
    ['Plátano', 'fruit', 'normal']
  ];
  const CATEGORY_LABELS = {
    protein: 'Proteína', protein_drink: 'Bebida proteica', protein_fat: 'Proteína/grasa',
    vegetable: 'Verdura', carb: 'Hidrato', fruit: 'Fruta', dairy: 'Lácteo',
    sweet: 'Dulce', drink: 'Bebida', other: 'Otro'
  };
  const PRIORITY_LABELS = {prefer: 'Prioritario', normal: 'Normal', secondary: 'Secundario', avoid: 'Evitar'};
  const STOCK_LABELS = {ok: 'Disponible', low: 'Queda poco', out: 'No hay'};

  let pantry = {items: []};
  let stats = {};
  let pantryFilter = 'all';
  let alternativeOffset = 0;
  let lastAlternativeUsed = [];

  const esc = (value) => String(value ?? '')
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');
  const norm = (value) => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();

  function currentDay() {
    const input = document.querySelector('#dashDate') || document.querySelector("input[type='date']");
    return input?.value || (typeof day === 'function' ? day() : new Date().toISOString().slice(0, 10));
  }

  function categoryOptions(selected) {
    return Object.entries(CATEGORY_LABELS).map(([value, label]) =>
      `<option value="${value}" ${value === selected ? 'selected' : ''}>${label}</option>`
    ).join('');
  }

  function priorityOptions(selected) {
    return Object.entries(PRIORITY_LABELS).map(([value, label]) =>
      `<option value="${value}" ${value === selected ? 'selected' : ''}>${label}</option>`
    ).join('');
  }

  function stockOptions(selected) {
    return Object.entries(STOCK_LABELS).map(([value, label]) =>
      `<option value="${value}" ${value === selected ? 'selected' : ''}>${label}</option>`
    ).join('');
  }

  function quickChip([name, category, priority]) {
    const existing = pantry.items.find((item) => norm(item.name) === norm(name));
    return `<button class="pantry-quick-chip ${existing?.available ? 'active' : ''}" onclick='pantryQuickAdd(${JSON.stringify(name)},${JSON.stringify(category)},${JSON.stringify(priority)})'>
      <span>${existing?.available ? '✓' : '+'}</span>${esc(name)}
    </button>`;
  }

  function itemCard(item) {
    const available = item.available && item.stock !== 'out';
    return `<article class="pantry-item-card ${available ? 'available' : 'out'}" data-pantry-item="${esc(item.id)}">
      <header>
        <label class="pantry-availability">
          <input type="checkbox" data-field="available" ${available ? 'checked' : ''} onchange="pantryAvailabilityChanged(this)">
          <span></span>
        </label>
        <div class="pantry-item-name"><input data-field="name" value="${esc(item.name)}" aria-label="Nombre"><small>${esc(CATEGORY_LABELS[item.category] || 'Otro')}</small></div>
        <button class="pantry-remove" onclick="pantryRemoveItem('${esc(item.id)}')" title="Eliminar">×</button>
      </header>
      <div class="pantry-item-fields">
        <label><span>Stock</span><select data-field="stock" onchange="pantryStockChanged(this)">${stockOptions(item.stock || (available ? 'ok' : 'out'))}</select></label>
        <label><span>Categoría</span><select data-field="category">${categoryOptions(item.category || 'other')}</select></label>
        <label><span>Uso</span><select data-field="priority">${priorityOptions(item.priority || 'normal')}</select></label>
      </div>
      <label class="pantry-notes"><span>Nota</span><input data-field="notes" value="${esc(item.notes || '')}" placeholder="Ej. medir en seco, proteína principal…"></label>
    </article>`;
  }

  function filteredItems() {
    const query = norm(document.querySelector('#pantrySearch')?.value || '');
    return (pantry.items || []).filter((item) => {
      if (query && !norm(`${item.name} ${item.category} ${item.notes}`).includes(query)) return false;
      if (pantryFilter === 'available') return item.available && item.stock !== 'out';
      if (pantryFilter === 'low') return item.stock === 'low';
      if (pantryFilter === 'out') return !item.available || item.stock === 'out';
      if (pantryFilter === 'avoid') return item.priority === 'avoid';
      return true;
    });
  }

  function renderItems() {
    const root = document.querySelector('#pantryItems');
    if (!root) return;
    const items = filteredItems();
    root.innerHTML = items.length
      ? items.map(itemCard).join('')
      : '<div class="pantry-empty"><b>No hay alimentos en este filtro</b><span>Añade uno arriba o cambia el filtro.</span></div>';
  }

  function renderStats() {
    const values = [
      ['Disponibles', stats.available || 0, 'good'],
      ['Queda poco', stats.low || 0, 'warn'],
      ['Sin stock', stats.out || 0, 'muted'],
      ['Prioritarios', stats.preferred || 0, 'info']
    ];
    const root = document.querySelector('#pantryStats');
    if (root) root.innerHTML = values.map(([label, value, tone]) =>
      `<span class="pantry-stat ${tone}"><b>${value}</b><small>${label}</small></span>`
    ).join('');
  }

  function readItemsFromDom() {
    const visible = new Map();
    document.querySelectorAll('[data-pantry-item]').forEach((card) => {
      const id = card.dataset.pantryItem;
      const get = (field) => card.querySelector(`[data-field="${field}"]`);
      const stock = get('stock')?.value || 'ok';
      visible.set(id, {
        id,
        name: get('name')?.value.trim() || 'Sin nombre',
        available: !!get('available')?.checked && stock !== 'out',
        stock,
        category: get('category')?.value || 'other',
        priority: get('priority')?.value || 'normal',
        notes: get('notes')?.value.trim() || ''
      });
    });
    pantry.items = pantry.items.map((item) => visible.get(item.id) || item);
    return pantry.items;
  }

  async function loadPantry() {
    const result = await api(ENDPOINT);
    pantry = result.pantry || {items: []};
    pantry.items = Array.isArray(pantry.items) ? pantry.items : [];
    stats = result.stats || {};
    renderStats();
    const quick = document.querySelector('#pantryQuick');
    if (quick) quick.innerHTML = COMMON.map(quickChip).join('');
    renderItems();
    const updated = document.querySelector('#pantryUpdated');
    if (updated) updated.textContent = pantry.updated_at ? `Actualizada ${pantry.updated_at.replace('T', ' ')}` : 'Todavía sin guardar desde la web';
  }

  function renderPantry() {
    document.body.classList.remove('dpp-strava-page');
    document.body.classList.add('dpp-pantry-page');
    setTitle('Despensa');
    document.querySelector('#view').innerHTML = `
      <section class="pantry-hero">
        <div><span class="pantry-kicker">COACH LOCAL · v0.0.19</span><h2>Tu despensa real</h2><p>Marca lo que tienes ahora. El Coach solo propondrá comidas con alimentos disponibles.</p></div>
        <div id="pantryStats" class="pantry-stats"></div>
      </section>

      <section class="card pantry-quick-card">
        <header><div><h3>Añadir o reactivar rápido</h3><p>Un toque activa los alimentos habituales.</p></div><small id="pantryUpdated"></small></header>
        <div id="pantryQuick" class="pantry-quick-list"></div>
        <div class="pantry-add-row">
          <input id="pantryNewName" placeholder="Otro alimento…" onkeydown="if(event.key==='Enter') pantryAddCustom()">
          <select id="pantryNewCategory">${categoryOptions('other')}</select>
          <button class="btn secondary" onclick="pantryAddCustom()">Añadir</button>
        </div>
      </section>

      <section class="pantry-toolbar">
        <div class="pantry-search"><span>⌕</span><input id="pantrySearch" placeholder="Buscar alimento…" oninput="pantryRefreshItems()"></div>
        <div class="pantry-filters">
          ${[['all','Todos'],['available','Disponibles'],['low','Queda poco'],['out','No hay'],['avoid','Evitar']].map(([id,label]) => `<button class="${id === pantryFilter ? 'active' : ''}" onclick="pantrySetFilter('${id}',this)">${label}</button>`).join('')}
        </div>
        <button class="btn pantry-save" onclick="pantrySave()">Guardar despensa</button>
      </section>

      <section id="pantryItems" class="pantry-items-grid"><div class="pantry-empty"><b>Cargando despensa…</b></div></section>
      <div class="pantry-mobile-save"><button class="btn" onclick="pantrySave()">Guardar cambios</button></div>`;
    loadPantry().catch((error) => toast(`Despensa: ${error.message}`));
  }

  window.pantryRefreshItems = renderItems;
  window.pantrySetFilter = function (filter, button) {
    readItemsFromDom();
    pantryFilter = filter;
    document.querySelectorAll('.pantry-filters button').forEach((node) => node.classList.toggle('active', node === button));
    renderItems();
  };
  window.pantryAvailabilityChanged = function (input) {
    const card = input.closest('[data-pantry-item]');
    const stock = card?.querySelector('[data-field="stock"]');
    if (stock && input.checked && stock.value === 'out') stock.value = 'ok';
    card?.classList.toggle('available', input.checked);
    card?.classList.toggle('out', !input.checked);
  };
  window.pantryStockChanged = function (select) {
    const card = select.closest('[data-pantry-item]');
    const check = card?.querySelector('[data-field="available"]');
    if (check) check.checked = select.value !== 'out';
    card?.classList.toggle('available', select.value !== 'out');
    card?.classList.toggle('out', select.value === 'out');
  };
  window.pantryQuickAdd = function (name, category, priority) {
    readItemsFromDom();
    const existing = pantry.items.find((item) => norm(item.name) === norm(name));
    if (existing) {
      existing.available = true;
      existing.stock = 'ok';
      existing.category = category || existing.category;
      existing.priority = priority || existing.priority;
    } else {
      pantry.items.unshift({id: `new-${Date.now()}`, name, available: true, stock: 'ok', category, priority, notes: ''});
    }
    document.querySelector('#pantryQuick').innerHTML = COMMON.map(quickChip).join('');
    renderItems();
  };
  window.pantryAddCustom = function () {
    readItemsFromDom();
    const input = document.querySelector('#pantryNewName');
    const name = input?.value.trim();
    if (!name) return toast('Escribe el nombre del alimento');
    const existing = pantry.items.find((item) => norm(item.name) === norm(name));
    if (existing) {
      existing.available = true;
      existing.stock = 'ok';
    } else {
      pantry.items.unshift({
        id: `new-${Date.now()}`, name, available: true, stock: 'ok',
        category: document.querySelector('#pantryNewCategory')?.value || 'other', priority: 'normal', notes: ''
      });
    }
    if (input) input.value = '';
    renderItems();
  };
  window.pantryRemoveItem = function (id) {
    readItemsFromDom();
    pantry.items = pantry.items.filter((item) => item.id !== id);
    renderItems();
  };
  window.pantrySave = async function () {
    try {
      const result = await api(ENDPOINT, {method: 'POST', body: JSON.stringify({items: readItemsFromDom()})});
      pantry = result.pantry;
      stats = result.stats || {};
      toast('Despensa guardada');
      renderStats();
      document.querySelector('#pantryQuick').innerHTML = COMMON.map(quickChip).join('');
      renderItems();
      document.querySelector('#pantryUpdated').textContent = `Actualizada ${pantry.updated_at.replace('T', ' ')}`;
    } catch (error) {
      toast(`Despensa: ${error.message}`);
    }
  };

  function applyAlternative(result) {
    const alternative = result.alternative || {};
    if (!alternative.primary) return;
    lastAlternativeUsed = alternative.pantry_used || [];
    const decision = document.querySelector('.dpp-coach-decision');
    const why = document.querySelector('.dpp-coach-why');
    const heroText = document.querySelector('.fi13-hero p');
    if (decision) decision.textContent = alternative.primary;
    if (why) why.textContent = alternative.why || '';
    if (heroText) heroText.textContent = alternative.primary;
    const actions = document.querySelector('.dpp-coach-actions-v019');
    if (actions) actions.dataset.used = JSON.stringify(lastAlternativeUsed);
    closeUnavailablePicker();
  }

  async function fetchCoachUsed() {
    if (lastAlternativeUsed.length) return lastAlternativeUsed;
    const result = await api(`/api/smart-coach/day?date=${encodeURIComponent(currentDay())}`);
    return result.coach?.pantry?.used || [];
  }

  window.coachAnotherMeal = async function () {
    try {
      const used = await fetchCoachUsed();
      alternativeOffset += 1;
      const result = await api('/api/smart-coach/alternative', {
        method: 'POST', body: JSON.stringify({date: currentDay(), exclude: used, offset: alternativeOffset})
      });
      applyAlternative(result);
      toast('Nueva opción preparada');
    } catch (error) {
      toast(`Coach: ${error.message}`);
    }
  };

  function closeUnavailablePicker() {
    document.querySelector('#coachUnavailablePicker')?.remove();
  }
  window.coachCloseUnavailable = closeUnavailablePicker;

  window.coachUnavailablePicker = async function () {
    try {
      closeUnavailablePicker();
      const used = await fetchCoachUsed();
      if (!used.length) {
        go('pantry');
        return toast('Actualiza la despensa para generar opciones concretas');
      }
      const root = document.querySelector('.dpp-coach-main');
      if (!root) return;
      root.insertAdjacentHTML('beforeend', `
        <div id="coachUnavailablePicker" class="coach-unavailable-picker">
          <div><b>¿Qué alimento no tienes?</b><button onclick="coachCloseUnavailable()">×</button></div>
          <p>Se marcará como “No hay” en la despensa y el Coach buscará otra combinación.</p>
          <div class="coach-unavailable-options">${used.map((name) => `<label><input type="checkbox" value="${esc(name)}"><span>${esc(name)}</span></label>`).join('')}</div>
          <button class="btn" onclick="coachConfirmUnavailable()">Marcar y buscar alternativa</button>
        </div>`);
    } catch (error) {
      toast(`Coach: ${error.message}`);
    }
  };

  window.coachConfirmUnavailable = async function () {
    const names = [...document.querySelectorAll('#coachUnavailablePicker input:checked')].map((input) => input.value);
    if (!names.length) return toast('Selecciona al menos un alimento');
    try {
      const result = await api('/api/smart-coach/unavailable', {
        method: 'POST', body: JSON.stringify({date: currentDay(), names, offset: alternativeOffset})
      });
      lastAlternativeUsed = [];
      applyAlternative(result);
      toast(result.message || 'Despensa actualizada');
    } catch (error) {
      toast(`Coach: ${error.message}`);
    }
  };

  function injectCoachActions() {
    const visual = document.querySelector('.dpp-coach-visual');
    if (!visual || visual.querySelector('.dpp-coach-actions-v019')) return;
    const actions = document.createElement('div');
    actions.className = 'dpp-coach-actions-v019';
    actions.innerHTML = `
      <button class="coach-action unavailable" onclick="coachUnavailablePicker()"><span>−</span><b>No tengo esto</b></button>
      <button class="coach-action alternative" onclick="coachAnotherMeal()"><span>↻</span><b>Dame otra comida</b></button>
      <button class="coach-action pantry" onclick="go('pantry')"><span>▦</span><b>Editar despensa</b></button>`;
    visual.appendChild(actions);
    visual.querySelector('.dpp-coach-signals')?.classList.add('dpp-coach-signals-hidden');
  }

  if (typeof PAGES !== 'undefined' && !PAGES.some((entry) => entry[0] === 'pantry')) {
    const foodIndex = PAGES.findIndex((entry) => entry[0] === 'foods');
    PAGES.splice(foodIndex >= 0 ? foodIndex + 1 : PAGES.length, 0, ['pantry', '🧺', 'Despensa']);
  }
  if (typeof UI5_NAV !== 'undefined') UI5_NAV.pantry = ['🧺', 'Despensa', 'Disponible ahora'];

  try {
    const previousRender = render;
    const wrappedRender = function () {
      document.body.classList.toggle('dpp-pantry-page', page === 'pantry');
      if (page === 'pantry') return renderPantry();
      return previousRender.apply(this, arguments);
    };
    window.render = wrappedRender;
    render = wrappedRender;
  } catch (error) {
    console.warn('Pantry v0.0.19 render wrapper', error);
  }

  try { renderNav(); } catch (error) {}

  const observer = new MutationObserver(() => injectCoachActions());
  observer.observe(document.documentElement, {childList: true, subtree: true});
  [200, 600, 1200, 2500].forEach((delay) => setTimeout(injectCoachActions, delay));

  document.title = 'Diet Pro Planner · v0.0.19';
  setTimeout(() => {
    const eyebrow = document.querySelector('.eyebrow');
    if (eyebrow) eyebrow.textContent = 'Dieta controlada · v0.0.19';
  }, 100);
})();
