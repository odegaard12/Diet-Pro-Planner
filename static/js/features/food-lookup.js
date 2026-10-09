/*
 * Diet Pro Planner · barcode / online food search for the "Alimentos" form.
 * Barcode: local catalog first, then Open Food Facts. Camera scanning uses the
 * browser's BarcodeDetector when available (Chrome/Android); manual entry always works.
 */
(function () {
  'use strict';

  let stream = null;
  let results = [];

  function mount(selector) {
    const host = document.querySelector(selector);
    if (!host) return;
    const canScan = 'BarcodeDetector' in window && navigator.mediaDevices?.getUserMedia;
    host.innerHTML = `<div class="lookup-box">
      <div><b>🔎 Buscar producto</b><small>Código de barras o nombre · Open Food Facts</small></div>
      <div class="lookup-row">
        <input id="lookupQuery" placeholder="8410000000000 o “yogur proteico”" autocomplete="off" inputmode="search" onkeydown="if(event.key==='Enter'){event.preventDefault();dppLookup()}">
        <button class="btn secondary" type="button" onclick="dppLookup(this)">Buscar</button>
        ${canScan ? '<button class="btn secondary" type="button" onclick="dppScan()" title="Escanear con la cámara">📷</button>' : ''}
      </div>
      <div id="lookupScanner" hidden><video id="lookupVideo" playsinline muted></video><button class="btn small danger" type="button" onclick="dppStopScan()">Cerrar cámara</button></div>
      <div id="lookupResults" class="lookup-results"></div>
    </div>`;
  }

  function resultCard(food, index) {
    const badges = [food.nutriscore ? `Nutri-Score ${esc(food.nutriscore)}` : '', food.nova ? `NOVA ${esc(food.nova)}` : '', food.complete === false ? 'datos incompletos' : ''].filter(Boolean);
    return `<button type="button" class="lookup-item" onclick="dppUseLookup(${index})">
      <b>${esc(food.name)}</b>
      <small>${fmt(food.kcal)} kcal · ${fmt(food.protein)} g prot · ${fmt(food.carbs)} g HC · ${fmt(food.fat)} g grasa /100 g${food.brand ? ' · ' + esc(food.brand) : ''}</small>
      ${badges.length ? `<span class="lookup-badges">${badges.map((b) => `<i>${b}</i>`).join('')}</span>` : ''}
    </button>`;
  }

  function showResults(list, note) {
    results = list;
    const box = document.querySelector('#lookupResults');
    if (!box) return;
    box.innerHTML = (note ? `<p class="muted">${esc(note)}</p>` : '') + (list.length ? list.map(resultCard).join('') : '<div class="empty">Sin resultados. Prueba otro nombre o rellena a mano.</div>');
  }

  async function lookupBarcode(code) {
    const r = await api(`/api/foods/barcode/${encodeURIComponent(code)}`);
    if (!r.found) return showResults([], `Código ${code} no encontrado en Open Food Facts.`);
    if (r.source === 'local') {
      fillFoodForm(r.food);
      showResults([], `Ya está en tu catálogo: “${r.food.name}”. Puedes editarlo y guardar.`);
      return;
    }
    showResults([r.food], r.cached ? 'Resultado guardado en caché local.' : 'Resultado de Open Food Facts: revisa y guarda.');
    window.dppUseLookup(0);
  }

  window.dppLookup = async function (btn) {
    const query = String(document.querySelector('#lookupQuery')?.value || '').trim();
    if (!query) return toast('Escribe un código de barras o un nombre');
    await busy(btn, async () => {
      const box = document.querySelector('#lookupResults');
      if (box) box.innerHTML = '<p class="muted">Buscando…</p>';
      if (/^\d{8,14}$/.test(query)) return lookupBarcode(query);
      const r = await api(`/api/foods/search-online?q=${encodeURIComponent(query)}`);
      showResults(r.results || []);
    });
  };

  window.dppUseLookup = function (index) {
    const food = results[index];
    if (!food) return;
    fillFoodForm({...food, notes: '', purchased: 1});
    toast('Datos cargados: revisa y pulsa Guardar alimento');
    document.querySelector('#fName')?.scrollIntoView({behavior: 'smooth', block: 'center'});
  };

  window.dppStopScan = function () {
    stream?.getTracks().forEach((t) => t.stop());
    stream = null;
    const box = document.querySelector('#lookupScanner');
    if (box) box.hidden = true;
  };

  window.dppScan = async function () {
    try {
      const detector = new window.BarcodeDetector({formats: ['ean_13', 'ean_8', 'upc_a', 'upc_e']});
      stream = await navigator.mediaDevices.getUserMedia({video: {facingMode: 'environment'}});
      const video = document.querySelector('#lookupVideo');
      document.querySelector('#lookupScanner').hidden = false;
      video.srcObject = stream;
      await video.play();
      const started = Date.now();
      const tick = async () => {
        if (!stream) return;
        try {
          const codes = await detector.detect(video);
          if (codes.length) {
            const code = codes[0].rawValue;
            window.dppStopScan();
            document.querySelector('#lookupQuery').value = code;
            return window.dppLookup();
          }
        } catch (e) { /* frame not ready */ }
        if (Date.now() - started > 30000) { window.dppStopScan(); return toast('No se detectó ningún código'); }
        requestAnimationFrame(tick);
      };
      tick();
    } catch (e) {
      window.dppStopScan();
      toast(`Cámara no disponible: ${e.message || e}`);
    }
  };

  document.addEventListener('visibilitychange', () => { if (document.hidden) window.dppStopScan(); });
  window.DPPFoodLookup = {mount};
})();
