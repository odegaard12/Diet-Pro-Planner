/* Diet Pro Planner v0.0.18 · Strava stability/settings UI */
(function () {
  'use strict';

  let stravaConfig = null;
  let stravaDiagnostics = null;

  const esc = (value) => String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  function currentCallback() {
    return window.location.origin + '/api/strava/callback';
  }

  function rateText(rate) {
    if (!rate || typeof rate !== 'object') return 'Sin datos de consumo todavía.';
    const usage = Array.isArray(rate.read_usage) && rate.read_usage.length ? rate.read_usage : rate.usage;
    const limit = Array.isArray(rate.read_limit) && rate.read_limit.length ? rate.read_limit : rate.limit;
    if (!Array.isArray(usage) || !Array.isArray(limit) || !usage.length || !limit.length) {
      return rate.status_code === 429
        ? `Límite temporal alcanzado · prueba de nuevo sobre las ${rate.next_reset_local || 'próximo cuarto de hora'}`
        : 'Strava todavía no devolvió información de límites.';
    }
    return `Lecturas: ${usage[0] || 0}/${limit[0] || '?'} en 15 min · ${usage[1] || 0}/${limit[1] || '?'} hoy`;
  }

  function statusTone(configured, connected) {
    return connected ? 'ok' : configured ? 'warn' : 'bad';
  }

  window.useCurrentStravaCallback = function () {
    const input = document.querySelector('#stravaRedirectUri');
    if (input) input.value = currentCallback();
    const domain = document.querySelector('#stravaCallbackDomain');
    if (domain) domain.textContent = new URL(currentCallback()).hostname;
  };

  window.toggleStravaSecret = function () {
    const input = document.querySelector('#stravaClientSecret');
    if (!input) return;
    input.type = input.type === 'password' ? 'text' : 'password';
  };

  window.loadStravaV018 = async function () {
    try {
      const [config, diagnostics, status, auto] = await Promise.all([
        api('/api/integrations/strava/config'),
        api('/api/integrations/strava/diagnostics'),
        api('/api/strava/status'),
        api('/api/strava/auto-status')
      ]);
      stravaConfig = config;
      stravaDiagnostics = diagnostics;
      window.__stravaConnectUrl = status.connect_url || '';

      const statusBox = document.querySelector('#stravaStatus');
      if (statusBox) {
        statusBox.innerHTML = `
          <div class="status ${statusTone(status.configured, status.connected)}">
            <b>${status.connected ? 'Conectado' : status.configured ? 'Configurado, falta conectar' : 'No configurado'}</b>
            <span>${status.connected ? 'Cuenta autorizada y lista para sincronizar.' : esc(status.message || 'Guarda la configuración para continuar.')}</span>
          </div>`;
      }

      const idInput = document.querySelector('#stravaClientId');
      const redirectInput = document.querySelector('#stravaRedirectUri');
      const domain = document.querySelector('#stravaCallbackDomain');
      const storage = document.querySelector('#stravaStorage');
      if (idInput) idInput.value = config.client_id || '';
      if (redirectInput) redirectInput.value = config.redirect_uri || config.suggested_redirect_uri || currentCallback();
      if (domain) domain.textContent = config.callback_domain || new URL(config.suggested_redirect_uri || currentCallback()).hostname;
      if (storage) storage.textContent = config.storage === 'data/integrations.json' ? 'Guardado privado en la Raspberry' : 'Cargado desde .env';

      const secretInput = document.querySelector('#stravaClientSecret');
      if (secretInput) secretInput.placeholder = config.client_secret_set ? '•••••••••••••••• (guardado)' : 'Pega el Client Secret';

      const diagnosticBox = document.querySelector('#stravaDiagnostics');
      if (diagnosticBox) {
        diagnosticBox.innerHTML = `
          <div class="strava-diagnostic-grid">
            <div><span>Credenciales</span><b>${diagnostics.configured ? 'Correctas' : 'Incompletas'}</b></div>
            <div><span>Autorización</span><b>${diagnostics.connected ? 'Conectado' : 'Pendiente'}</b></div>
            <div><span>Permisos</span><b>${esc(diagnostics.scope || 'Sin token')}</b></div>
            <div><span>Consumo API</span><b>${esc(rateText(diagnostics.rate))}</b></div>
          </div>`;
      }

      const autoBox = document.querySelector('#stravaAutoStatus');
      if (autoBox) {
        const result = auto.last_result || {};
        autoBox.innerHTML = `
          <div class="status ${auto.enabled ? 'ok' : 'warn'}">
            <b>${auto.enabled ? 'Auto-sync activado' : 'Auto-sync desactivado'}</b>
            <span>${esc(auto.last_message || 'Aún no sincronizado')}</span>
          </div>
          <p class="muted">Último resultado: ${fmt(result.imported || 0)} nuevas · ${fmt(result.skipped || 0)} ya existentes · ${fmt(result.details_requested || 0)} detalles consultados</p>`;
      }
      const enabled = document.querySelector('#stravaAutoEnabled');
      const interval = document.querySelector('#stravaAutoInterval');
      const from = document.querySelector('#stravaAutoFrom');
      if (enabled) enabled.checked = !!auto.enabled;
      if (interval) interval.value = String(auto.interval_minutes || 180);
      if (from) from.value = auto.after_date || auto.latest_import_date || today();
    } catch (error) {
      const statusBox = document.querySelector('#stravaStatus');
      if (statusBox) statusBox.innerHTML = `<div class="empty">No se pudo cargar Strava: ${esc(error.message)}</div>`;
    }
  };

  window.saveStravaWebConfig = async function () {
    const clientId = document.querySelector('#stravaClientId')?.value.trim() || '';
    const clientSecret = document.querySelector('#stravaClientSecret')?.value.trim() || '';
    const redirectUri = document.querySelector('#stravaRedirectUri')?.value.trim() || currentCallback();
    try {
      const result = await api('/api/integrations/strava/config', {
        method: 'POST',
        body: JSON.stringify({client_id: clientId, client_secret: clientSecret, redirect_uri: redirectUri})
      });
      toast(result.message || 'Configuración guardada');
      await loadStravaV018();
    } catch (error) {
      toast('Configuración Strava: ' + error.message);
    }
  };

  window.testStravaConnection = async function () {
    const button = document.querySelector('#stravaTestButton');
    if (button) button.disabled = true;
    try {
      const result = await api('/api/integrations/strava/test', {method: 'POST', body: '{}'});
      const athlete = result.athlete || {};
      toast(`Strava correcto${athlete.firstname ? ': ' + athlete.firstname : ''}`);
      await loadStravaV018();
    } catch (error) {
      toast('Prueba Strava: ' + error.message);
    } finally {
      if (button) button.disabled = false;
    }
  };

  window.disconnectStravaWeb = async function () {
    if (!confirm('¿Desconectar Strava? Se conservarán las credenciales y se hará copia del token.')) return;
    try {
      const result = await api('/api/integrations/strava/disconnect', {method: 'POST', body: '{}'});
      toast(result.message || 'Strava desconectado');
      await loadStravaV018();
    } catch (error) {
      toast('Strava: ' + error.message);
    }
  };

  window.connectStrava = function () {
    if (!window.__stravaConnectUrl) {
      toast('Guarda primero la configuración Strava en esta pantalla');
      return;
    }
    window.location.href = window.__stravaConnectUrl;
  };

  window.previewStrava = async function () {
    const afterDate = document.querySelector('#stravaFrom')?.value;
    const beforeDate = document.querySelector('#stravaTo')?.value;
    const list = document.querySelector('#stravaList');
    if (list) list.innerHTML = '<div class="empty">Buscando actividades… solo 1 llamada de listado.</div>';
    try {
      const result = await api('/api/strava/preview', {
        method: 'POST',
        body: JSON.stringify({after_date: afterDate, before_date: beforeDate})
      });
      __stravaPreview = result.activities || [];
      renderStravaPreview();
      const info = document.querySelector('#stravaRequestInfo');
      if (info) info.textContent = `${result.received || 0} actividades · ${result.details_requested || 0} detalles consultados · ${rateText(result.rate)}`;
    } catch (error) {
      if (list) list.innerHTML = `<div class="empty">Strava: ${esc(error.message)}</div>`;
    }
  };

  window.importSelectedStrava = async function () {
    const ids = [...document.querySelectorAll('[data-strava-id]:checked')].map((input) => input.dataset.stravaId);
    if (!ids.length) {
      toast('No seleccionaste actividades nuevas');
      return;
    }
    try {
      const result = await api('/api/strava/import', {
        method: 'POST',
        body: JSON.stringify({
          after_date: document.querySelector('#stravaFrom')?.value,
          before_date: document.querySelector('#stravaTo')?.value,
          ids
        })
      });
      toast(`Importadas: ${result.imported || 0} · existentes: ${result.skipped || 0} · detalles: ${result.details_requested || 0}`);
      await load();
      page = 'integrations';
      renderNav();
      render();
    } catch (error) {
      toast('Strava: ' + error.message);
    }
  };

  window.saveStravaAutoConfig = async function () {
    try {
      const result = await api('/api/strava/auto-config', {
        method: 'POST',
        body: JSON.stringify({
          enabled: !!document.querySelector('#stravaAutoEnabled')?.checked,
          after_date: document.querySelector('#stravaAutoFrom')?.value,
          interval_minutes: document.querySelector('#stravaAutoInterval')?.value || 180
        })
      });
      toast(result.last_message || 'Auto-sync guardado');
      await loadStravaV018();
    } catch (error) {
      toast('Auto-sync: ' + error.message);
    }
  };

  window.runStravaAutoNow = async function () {
    const box = document.querySelector('#stravaAutoStatus');
    if (box) box.innerHTML = '<div class="empty">Sincronizando solo actividades recientes…</div>';
    try {
      const result = await api('/api/strava/auto-run', {method: 'POST', body: '{}'});
      toast(result.message || `Importadas: ${result.imported || 0}`);
      await load();
      page = 'integrations';
      renderNav();
      render();
    } catch (error) {
      toast('Auto-sync: ' + error.message);
      await loadStravaV018();
    }
  };

  renderIntegrations = function () {
    const to = today();
    const from = new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 10);
    document.querySelector('#view').innerHTML = `
      <section class="strava-v018-head">
        <div><span class="ui5-kicker">Integración local · v0.0.18</span><h2>Strava estable y controlado</h2><p>Configura, conecta, prueba y sincroniza desde aquí. Las claves nunca se muestran después de guardarlas.</p></div>
        <div id="stravaStatus" class="empty">Comprobando Strava…</div>
      </section>

      <div class="grid cols-2 strava-v018-grid">
        <section class="card integration-card">
          <div class="section-title compact-title"><div><h3>🔐 Configuración Strava</h3><p id="stravaStorage">Solo red local</p></div></div>
          <div class="row">
            <div class="field span-4"><label>Client ID</label><input id="stravaClientId" inputmode="numeric" autocomplete="off" placeholder="ID numérico"></div>
            <div class="field span-8"><label>Client Secret</label><div class="strava-secret-row"><input id="stravaClientSecret" type="password" autocomplete="new-password"><button class="btn secondary small" type="button" onclick="toggleStravaSecret()">Ver</button></div><small>Déjalo vacío para conservar el secreto guardado.</small></div>
            <div class="field span-12"><label>Callback URL</label><input id="stravaRedirectUri" autocomplete="off"><div class="strava-inline-help"><button class="btn secondary small" type="button" onclick="useCurrentStravaCallback()">Usar esta dirección</button><span>En Strava, Authorization Callback Domain debe ser: <b id="stravaCallbackDomain">—</b></span></div></div>
          </div>
          <div class="action-row">
            <button class="btn" onclick="saveStravaWebConfig()">Guardar configuración</button>
            <button class="btn secondary" onclick="connectStrava()">Conectar / renovar permisos</button>
            <button id="stravaTestButton" class="btn secondary" onclick="testStravaConnection()">Probar conexión</button>
            <button class="btn danger" onclick="disconnectStravaWeb()">Desconectar</button>
          </div>
          <p class="muted">Se guarda en <code>data/integrations.json</code>, privado y fuera de Git. No hace falta editar <code>.env</code> para cambios futuros.</p>
        </section>

        <section class="card">
          <div class="section-title compact-title"><div><h3>🩺 Diagnóstico</h3><p>Estado real, permisos y límites</p></div></div>
          <div id="stravaDiagnostics" class="empty">Leyendo diagnóstico…</div>
          <div class="strava-note"><b>Sin puente PowerShell</b><p>Abre Diet Pro Planner por su dirección LAN, pulsa “Usar esta dirección” y copia únicamente el dominio indicado en la aplicación API de Strava.</p></div>
        </section>
      </div>

      <div class="grid cols-2 strava-v018-grid">
        <section class="card integration-card">
          <div class="section-title compact-title"><div><h3>📥 Actividades</h3><p>La búsqueda ya no descarga el detalle de todas las actividades.</p></div></div>
          <div class="row">
            <div class="field span-4"><label>Desde</label><input id="stravaFrom" type="date" value="${from}"></div>
            <div class="field span-4"><label>Hasta</label><input id="stravaTo" type="date" value="${to}"></div>
            <div class="field span-4"><label>&nbsp;</label><button class="btn secondary" onclick="previewStrava()">Buscar actividades</button></div>
          </div>
          <p id="stravaRequestInfo" class="muted">Se consultará el detalle solo de las actividades nuevas que selecciones.</p>
          <div id="stravaList" style="margin-top:14px"></div>
        </section>

        <section class="card note-box">
          <div class="section-title compact-title"><div><h3>⚙️ Auto-sync protegido</h3><p>Ventana reciente, caché y bloqueo de concurrencia</p></div></div>
          <div id="stravaAutoStatus" class="empty">Comprobando auto-sync…</div>
          <div class="row" style="margin-top:12px">
            <div class="field span-5"><label>Fecha mínima</label><input id="stravaAutoFrom" type="date" value="${from}"></div>
            <div class="field span-4"><label>Cada</label><select id="stravaAutoInterval"><option value="60">1 hora</option><option value="180" selected>3 horas</option><option value="360">6 horas</option><option value="720">12 horas</option></select></div>
            <div class="field span-3"><label>&nbsp;</label><button class="btn secondary" onclick="runStravaAutoNow()">Sincronizar ahora</button></div>
          </div>
          <label class="check-line"><input id="stravaAutoEnabled" type="checkbox"> Sincronizar automáticamente solo actividades nuevas</label>
          <div class="action-row"><button class="btn" onclick="saveStravaAutoConfig()">Guardar auto-sync</button></div>
          <p class="muted">Recomendado: cada 3 horas. Las actividades ya importadas no consumen llamadas de detalle.</p>
        </section>
      </div>`;
    loadStravaV018();
  };

  const params = new URLSearchParams(window.location.search);
  if (params.get('strava') === 'connected') {
    setTimeout(() => {
      page = 'integrations';
      renderNav();
      render();
      toast('Strava conectado correctamente');
      history.replaceState({}, '', window.location.pathname);
    }, 50);
  }
})();
