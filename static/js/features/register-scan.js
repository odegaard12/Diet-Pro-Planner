/* Registrar: add a product by barcode (v0.5.1). Type or paste the digits in the search box; the camera is optional. */
(function () {
  'use strict';

  const BARCODE = /^\d{8,14}$/;
  const canScan = () => 'BarcodeDetector' in window && !!navigator.mediaDevices?.getUserMedia;
  let stream = null;

  async function addByBarcode(code) {
    const local = state.foods.find((f) => String(f.barcode || '') === code);
    if (local) return addFood(local.id);
    const r = await api(`/api/foods/barcode/${encodeURIComponent(code)}`);
    if (!r.found) { toast(`Código ${code} no encontrado. Créalo en Alimentos.`); return null; }
    const f = r.food;
    if (r.source !== 'local') {
      if (f.complete === false) {
        go('foods'); fillFoodForm({...f, notes: '', purchased: 1}); window.openFoodForm?.();
        toast('Datos incompletos en Open Food Facts: revísalos y guarda');
        return null;
      }
      // foods.name is unique and saving an existing name overwrites it: never clobber a food that has another barcode.
      const taken = foodByName(f.name);
      const name = taken && String(taken.barcode || '') !== code ? `${f.name} · ${f.brand || code}` : f.name;
      await api('/api/foods', {method: 'POST', body: JSON.stringify({name, brand: f.brand || '', kcal: f.kcal, protein: f.protein, carbs: f.carbs, fat: f.fat, sugar: f.sugar || 0, salt: f.salt || 0, typical_g: f.typical_g || 100, purchased: true, source_note: f.source_note || 'Open Food Facts', notes: '', barcode: code})});
    }
    await load();
    const saved = state.foods.find((x) => String(x.barcode || '') === code);
    if (!saved) { toast('No se pudo añadir; búscalo en Alimentos'); return null; }
    toast(`Añadido: ${saved.name}`);
    return addFood(saved.id);
  }
  window.dppAddByBarcode = (code) => addByBarcode(String(code)).catch((e) => toast(e.message || 'No se pudo buscar el código'));

  function stopScan() {
    stream?.getTracks().forEach((t) => t.stop());
    stream = null;
    document.querySelector('#regScan')?.remove();
  }

  async function scan() {
    try {
      const detector = new window.BarcodeDetector({formats: ['ean_13', 'ean_8', 'upc_a', 'upc_e']});
      stream = await navigator.mediaDevices.getUserMedia({video: {facingMode: 'environment'}});
      document.body.insertAdjacentHTML('beforeend', '<div id="regScan" class="reg-scan"><video playsinline muted></video><button class="btn danger" type="button" onclick="dppStopRegScan()">Cerrar cámara</button></div>');
      const video = document.querySelector('#regScan video');
      video.srcObject = stream;
      await video.play();
      const started = Date.now();
      const tick = async () => {
        if (!stream) return;
        try {
          const codes = await detector.detect(video);
          if (codes.length) { const code = codes[0].rawValue; stopScan(); return window.dppAddByBarcode(code); }
        } catch (e) { /* frame not ready */ }
        if (Date.now() - started > 30000) { stopScan(); toast('No se detectó ningún código'); return; }
        requestAnimationFrame(tick);
      };
      tick();
    } catch (e) { stopScan(); toast(`Cámara no disponible: ${e.message || e}`); }
  }
  window.dppStopRegScan = stopScan;
  window.dppRegScan = scan;

  const baseSuggest = window.renderSuggestions;
  window.renderSuggestions = function () {
    baseSuggest();
    const q = String(document.querySelector('#foodSearch')?.value || '').trim();
    const box = document.querySelector('#suggestions');
    if (box && BARCODE.test(q)) {
      box.insertAdjacentHTML('afterbegin', `<button type="button" onclick="dppAddByBarcode('${q}')"><b>Añadir producto con el código ${esc(q)}</b><br><small class="muted">Tu catálogo y, si no está, Open Food Facts</small></button>`);
    }
  };

  const baseRegister = window.renderRegister;
  window.renderRegister = function () {
    baseRegister();
    const input = document.querySelector('#foodSearch');
    if (!input) return;
    input.placeholder = 'pollo, yogur… o código de barras';
    input.inputMode = 'search';
    if (canScan()) input.insertAdjacentHTML('afterend', '<button class="btn secondary scan-btn" type="button" onclick="dppRegScan()">Escanear código</button>');
  };
  document.addEventListener('visibilitychange', () => { if (document.hidden) stopScan(); });
})();
