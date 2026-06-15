/* Diet Pro Planner v0.0.18 · polished Strava integration */
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

  function rateParts(rate) {
    if (!rate || typeof rate !== 'object') return null;
    const usage = Array.isArray(rate.read_usage) && rate.read_usage.length ? rate.read_usage : rate.usage;
    const limit = Array.isArray(rate.read_limit) && rate.read_limit.length ? rate.read_limit : rate.limit;
    if (!Array.isArray(usage) || !Array.isArray(limit) || !usage.length || !limit.length) return null;
    return {
      shortUsed: Number(usage[0] || 0),
      shortLimit: Number(limit[0] || 0),
      dailyUsed: Number(usage[1] || 0),
      dailyLimit: Number(limit[1] || 0),
      reset: rate.next_reset_local || ''
    };
  }

  function rateText(rate) {
    const parts = rateParts(rate);
    if (!parts) {
      return rate && rate.status_code === 429
        ? `Límite temporal alcanzado · disponible sobre las ${rate.next_reset_local || 'próximo cuarto de hora'}`
        : 'Consumo disponible después de la primera consulta.';
    }
    return `${parts.shortUsed}/${parts.shortLimit || '?'} en 15 min · ${parts.dailyUsed}/${parts.dailyLimit || '?'} hoy`;
  }

  function rateShort(rate) {
    const parts = rateParts(rate);
    if (!parts) return 'API sin medir';
    return `API ${parts.shortUsed}/${parts.shortLimit || '?'}`;
  }

  function statusTone(configured, connected) {
    return connected ? 'ok' : configured ? 'warn' : 'bad';
  }

  function setText(selector, value) {
    const node = document.querySelector(selector);
    if (node) node.textContent = value;
  }

  function setStatusPill(selector, tone, eyebrow, value) {
    const node = document.querySelector(selector);
    if (!node) return;
    node.className = `strava-status-pill ${tone}`;
    node.innerHTML = `<span>${esc(eyebrow)}</span><b>${esc(value)}</b>`;
  }

  function syncBodyClass() {
    document.body.classList.toggle('dpp-strava-page', page === 'integrations');
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
    const button = document.querySelector('#stravaSecretToggle');
    if (button) button.textContent = input.type === 'password' ? 'Mostrar' : 'Ocultar';
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

      const connectionLabel = status.connected
        ? 'Conectado'
        : status.configured
          ? 'Pendiente de autorizar'
          : 'Sin configurar';
      const connectionDetail = status.connected
        ? 'Cuenta autorizada · permisos de actividades activos'
        : status.message || 'Abre la configuración avanzada para continuar.';

      setStatusPill('#stravaConnectionPill', statusTone(status.configured, status.connected), 'Conexión', connectionLabel);
      setStatusPill('#stravaApiPill', diagnostics.rate?.status_code === 429 ? 'warn' : 'neutral', 'Consumo', rateShort(diagnostics.rate));
      setStatusPill('#stravaAutoPill', auto.enabled ? 'ok' : 'neutral', 'Auto-sync', auto.enabled ? 'Activo' : 'Desactivado');
      setText('#stravaConnectionDetail', connectionDetail);
      setText('#stravaRateSummary', rateText(diagnostics.rate));
      setText('#stravaLastSync', auto.last_success_at ? `Última sincronización: ${auto.last_success_at}` : 'Todavía sin sincronización automática');

      const idInput = document.querySelector('#stravaClientId');
      const redirectInput = document.querySelector('#stravaRedirectUri');
      const domain = document.querySelector('#stravaCallbackDomain');
      const storage = document.querySelector('#stravaStorage');
      if (idInput) idInput.value = config.client_id || '';
      if (redirectInput) redirectInput.value = config.redirect_uri || config.suggested_redirect_uri || currentCallback();
      if (domain) domain.textContent = config.callback_domain || new URL(config.suggested_redirect_uri || currentCallback()).hostname;
      if (storage) storage.textContent = config.storage === 'data/integrations.json' ? 'Guardado local' : 'Usando .env';

      const secretInput = document.querySelector('#stravaClientSecret');
      if (secretInput) secretInput.placeholder = config.client_secret_set ? 'Secreto guardado · dejar vacío para conservar' : 'Pega el Client Secret';

      const diagnosticBox = document.querySelector('#stravaDiagnostics');
      if (diagnosticBox) {
        diagnosticBox.innerHTML = `
          <div class="strava-diagnostic-grid">
            <div><span>Credenciales</span><b>${diagnostics.configured ? 'Correctas' : 'Incompletas'}</b></div>
            <div><span>Autorización</span><b>${diagnostics.connected ? 'Activa' : 'Pendiente'}</b></div>
            <div><span>Permisos</span><b>${esc(diagnostics.scope || 'Sin token')}</b></div>
            <div><span>Uso API</span><b>${esc(rateText(diagnostics.rate))}</b></div>
          </div>`;
      }

      const settingsPanel = document.querySelector('#stravaSettingsPanel');
      if (settingsPanel && !status.configured) settingsPanel.open = true;

      const result = auto.last_result || {};
      const autoBox = document.querySelector('#stravaAutoStatus');
      if (autoBox) {
        autoBox.innerHTML = `
          <div class="strava-auto-result">
            <b>${auto.enabled ? 'Sincronización automática activa' : 'Sincronización automática desactivada'}</b>
            <span>${esc(auto.last_message || 'Sin actividad todavía')}</span>
            <small>${fmt(result.imported || 0)} nuevas · ${fmt(result.skipped || 0)} ya existentes · ${fmt(result.details_requested || 0)} detalles</small>
          </div>`;
      }

      const enabled = document.querySelector('#stravaAutoEnabled');
      const interval = document.querySelector('#stravaAutoInterval');
      const from = document.querySelector('#stravaAutoFrom');
      if (enabled) enabled.checked = !!auto.enabled;
      if (interval) {
        const valid = ['30', '60', '180', '360', '720'];
        const value = String(auto.interval_minutes || 180);
        interval.value = valid.includes(value) ? value : '180';
      }
      if (from) from.value = auto.after_date || auto.latest_import_date || today();
    } catch (error) {
      setStatusPill('#stravaConnectionPill', 'bad', 'Conexión', 'Error');
      setText('#stravaConnectionDetail', `No se pudo cargar el estado: ${error.message}`);
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
      toast(`Conexión correcta${athlete.firstname ? ': ' + athlete.firstname : ''}`);
      await loadStravaV018();
    } catch (error) {
      toast('Prueba Strava: ' + error.message);
    } finally {
      if (button) button.disabled = false;
    }
  };

  window.disconnectStravaWeb = async function () {
    if (!confirm('¿Desconectar Strava? Las credenciales se conservarán y se hará copia del token.')) return;
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
      const panel = document.querySelector('#stravaSettingsPanel');
      if (panel) panel.open = true;
      toast('Guarda primero la configuración');
      return;
    }
    window.location.href = window.__stravaConnectUrl;
  };

  function activityRow(activity, selectable) {
    const title = activity.title || activity.sport_type || activity.type || 'Actividad';
    const sport = activity.sport_type || activity.type || 'Strava';
    const state = activity.already_imported ? 'Importada' : 'Nueva';
    const stateClass = activity.already_imported ? 'done' : 'new';
    return `
      <article class="strava-activity-row ${stateClass}">
        <div class="strava-activity-date"><b>${esc(activity.date || '')}</b><span>${esc(activity.time || '')}</span></div>
        <div class="strava-activity-main"><b>${esc(title)}</b><span>${esc(sport)} · ${fmt(activity.minutes)} min${Number(activity.distance_km || 0) ? ` · ${fmt(activity.distance_km)} km` : ''}</span></div>
        <div class="strava-activity-energy"><b>~${fmt(activity.kcal)} kcal</b><span>vista rápida</span></div>
        <div class="strava-activity-state"><span class="strava-state ${stateClass}">${state}</span>${selectable ? `<input type="checkbox" data-strava-id="${esc(activity.id)}" checked aria-label="Seleccionar ${esc(title)}">` : ''}</div>
      </article>`;
  }

  function renderPreviewV018() {
    const list = document.querySelector('#stravaList');
    if (!list) return;
    const activities = Array.isArray(__stravaPreview) ? __stravaPreview : [];
    if (!activities.length) {
      list.innerHTML = '<div class="strava-empty-state"><b>Sin actividades</b><span>No hay resultados en el rango seleccionado.</span></div>';
      return;
    }

    const pending = activities.filter((activity) => !activity.already_imported);
    const imported = activities.filter((activity) => activity.already_imported);

    list.innerHTML = `
      <div class="strava-list-head">
        <div><b>${pending.length ? `${pending.length} actividades nuevas` : 'Todo al día'}</b><span>${activities.length} encontradas en total</span></div>
        ${pending.length ? `<button class="btn" onclick="importSelectedStrava()">Importar ${pending.length}</button>` : ''}
      </div>
      ${pending.length ? `<div class="strava-activity-list">${pending.map((activity) => activityRow(activity, true)).join('')}</div>` : '<div class="strava-empty-state success"><b>No hay nada pendiente</b><span>Las actividades de este intervalo ya están guardadas.</span></div>'}
      ${imported.length ? `<details class="strava-imported-details"><summary><span>Ya importadas</span><b>${imported.length}</b></summary><div class="strava-activity-list imported">${imported.map((activity) => activityRow(activity, false)).join('')}</div></details>` : ''}`;
  }

  window.renderStravaPreview = renderPreviewV018;
  try { renderStravaPreview = renderPreviewV018; } catch (error) {}

  window.previewStrava = async function () {
    const afterDate = document.querySelector('#stravaFrom')?.value;
    const beforeDate = document.querySelector('#stravaTo')?.value;
    const list = document.querySelector('#stravaList');
    if (list) list.innerHTML = '<div class="strava-empty-state loading"><b>Consultando Strava</b><span>La búsqueda usa una sola llamada y no descarga detalles.</span></div>';
    try {
      const result = await api('/api/strava/preview', {
        method: 'POST',
        body: JSON.stringify({after_date: afterDate, before_date: beforeDate})
      });
      __stravaPreview = result.activities || [];
      renderPreviewV018();
      setText('#stravaRequestInfo', `${result.received || 0} actividades · ${result.details_requested || 0} detalles · ${rateText(result.rate)}`);
      setStatusPill('#stravaApiPill', 'neutral', 'Consumo', rateShort(result.rate));
      setText('#stravaRateSummary', rateText(result.rate));
    } catch (error) {
      if (list) list.innerHTML = `<div class="strava-empty-state error"><b>No se pudo consultar Strava</b><span>${esc(error.message)}</span></div>`;
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
      toast(`Importadas: ${result.imported || 0} · detalles consultados: ${result.details_requested || 0}`);
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
    if (box) box.innerHTML = '<div class="strava-auto-result"><b>Sincronizando…</b><span>Solo se consultarán actividades recientes y nuevas.</span></div>';
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

  function renderIntegrationsV018() {
    syncBodyClass();
    const to = today();
    const from = new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 10);

    document.querySelector('#view').innerHTML = `
      <section class="strava-overview">
        <div class="strava-overview-title">
          <div class="strava-mark">S</div>
          <div><span>Integración deportiva</span><h2>Strava</h2><p id="stravaConnectionDetail">Comprobando conexión…</p></div>
        </div>
        <div class="strava-overview-status">
          <div id="stravaConnectionPill" class="strava-status-pill neutral"><span>Conexión</span><b>Comprobando</b></div>
          <div id="stravaApiPill" class="strava-status-pill neutral"><span>Consumo</span><b>API sin medir</b></div>
          <div id="stravaAutoPill" class="strava-status-pill neutral"><span>Auto-sync</span><b>Comprobando</b></div>
        </div>
      </section>

      <div class="strava-workspace">
        <section class="card strava-activities-card">
          <header class="strava-card-head">
            <div><span class="strava-section-kicker">ACTIVIDADES</span><h3>Importar desde Strava</h3><p>Busca primero; el detalle exacto solo se consulta al importar una actividad nueva.</p></div>
          </header>
          <div class="strava-searchbar">
            <label><span>Desde</span><input id="stravaFrom" type="date" value="${from}"></label>
            <label><span>Hasta</span><input id="stravaTo" type="date" value="${to}"></label>
            <button class="btn" onclick="previewStrava()">Buscar</button>
          </div>
          <div class="strava-request-line"><span id="stravaRequestInfo">Sin consulta reciente</span><small>Las kcal de la búsqueda son una vista rápida; al importar se guarda el detalle de Strava.</small></div>
          <div id="stravaList"><div class="strava-empty-state"><b>Listo para buscar</b><span>Selecciona un intervalo corto para revisar actividades.</span></div></div>
        </section>

        <aside class="card strava-auto-card">
          <header class="strava-card-head compact"><div><span class="strava-section-kicker">AUTOMATIZACIÓN</span><h3>Auto-sync</h3><p id="stravaLastSync">Comprobando…</p></div></header>
          <div id="stravaAutoStatus" class="strava-auto-status"></div>
          <label class="strava-switch-row"><span><b>Sincronizar automáticamente</b><small>Solo actividades nuevas</small></span><input id="stravaAutoEnabled" type="checkbox"></label>
          <div class="strava-auto-fields">
            <label><span>Cada</span><select id="stravaAutoInterval"><option value="30">30 min</option><option value="60">1 hora</option><option value="180" selected>3 horas</option><option value="360">6 horas</option><option value="720">12 horas</option></select></label>
            <label><span>Desde</span><input id="stravaAutoFrom" type="date" value="${from}"></label>
          </div>
          <div class="strava-auto-actions"><button class="btn" onclick="saveStravaAutoConfig()">Guardar</button><button class="btn secondary" onclick="runStravaAutoNow()">Sincronizar ahora</button></div>
          <div class="strava-api-meter"><span id="stravaRateSummary">Consumo disponible después de consultar</span></div>
        </aside>
      </div>

      <details id="stravaSettingsPanel" class="card strava-settings-panel">
        <summary><div><span class="strava-settings-icon">⚙</span><span><b>Configuración y diagnóstico</b><small>Credenciales, callback, permisos y conexión</small></span></div><em id="stravaStorage">Solo red local</em></summary>
        <div class="strava-settings-body">
          <section class="strava-settings-form">
            <div class="strava-settings-intro"><h3>Credenciales de la aplicación</h3><p>Se guardan únicamente en la Raspberry. El secreto no vuelve a mostrarse después de guardarlo.</p></div>
            <div class="row">
              <div class="field span-4"><label>Client ID</label><input id="stravaClientId" inputmode="numeric" autocomplete="off" placeholder="ID numérico"></div>
              <div class="field span-8"><label>Client Secret</label><div class="strava-secret-row"><input id="stravaClientSecret" type="password" autocomplete="new-password"><button id="stravaSecretToggle" class="btn secondary small" type="button" onclick="toggleStravaSecret()">Mostrar</button></div></div>
              <div class="field span-12"><label>Callback URL</label><input id="stravaRedirectUri" autocomplete="off"><div class="strava-inline-help"><button class="btn secondary small" type="button" onclick="useCurrentStravaCallback()">Usar dirección actual</button><span>En Strava configura como Callback Domain: <b id="stravaCallbackDomain">—</b></span></div></div>
            </div>
            <div class="action-row strava-settings-actions"><button class="btn" onclick="saveStravaWebConfig()">Guardar</button><button class="btn secondary" onclick="connectStrava()">Conectar / renovar</button><button id="stravaTestButton" class="btn secondary" onclick="testStravaConnection()">Probar</button><button class="btn danger" onclick="disconnectStravaWeb()">Desconectar</button></div>
          </section>
          <section class="strava-diagnostics-panel"><h3>Diagnóstico</h3><div id="stravaDiagnostics" class="empty">Leyendo estado…</div><p>Archivo privado: <code>data/integrations.json</code>. No se sube al repositorio.</p></section>
        </div>
      </details>`;

    loadStravaV018();
  }

  window.renderIntegrations = renderIntegrationsV018;
  try { renderIntegrations = renderIntegrationsV018; } catch (error) {}

  try {
    const previousRender = window.render || render;
    const wrappedRender = function () {
      syncBodyClass();
      return previousRender.apply(this, arguments);
    };
    window.render = wrappedRender;
    render = wrappedRender;
  } catch (error) {}

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
