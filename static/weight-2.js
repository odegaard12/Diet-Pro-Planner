(function () {
  'use strict';

  const metricLabels = {
    weight: 'Peso oficial',
    body_fat_pct: 'Grasa',
    fat_mass_kg: 'Masa grasa',
    water_pct: 'Agua',
    muscle_mass_kg: 'Músculo',
    skeletal_muscle_kg: 'Músculo esq.',
    visceral_fat: 'Visceral',
    bmr_kcal: 'BMR',
    biocharge: 'BioCharge',
  };

  const metricUnits = {
    weight: 'kg',
    body_fat_pct: '%',
    fat_mass_kg: 'kg',
    water_pct: '%',
    muscle_mass_kg: 'kg',
    skeletal_muscle_kg: 'kg',
    visceral_fat: '',
    bmr_kcal: 'kcal',
    biocharge: '',
  };

  let currentDays = 30;

  function fmt(value, digits) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
    return Number(value).toLocaleString('es-ES', {
      maximumFractionDigits: digits ?? 1,
      minimumFractionDigits: 0,
    });
  }

  function unit(name) {
    return metricUnits[name] || '';
  }

  function typeLabel(type) {
    const labels = {
      weight: 'Peso',
      composition: 'Composición',
      recovery: 'Recuperación',
      system: 'Sistema',
    };
    return labels[type] || 'Insight';
  }

  function trendText(delta, suffix) {
    if (delta === null || delta === undefined || Number.isNaN(Number(delta))) {
      return 'Sin tendencia suficiente';
    }
    const sign = Number(delta) > 0 ? '+' : '';
    return `Cambio desde primera lectura: ${sign}${fmt(delta, 2)} ${suffix || ''}`.trim();
  }

  function metricCell(row, name, suffix, digits) {
    const metric = row.metrics && row.metrics[name];
    if (!metric || metric.value === null || metric.value === undefined || Number.isNaN(Number(metric.value))) {
      return '—';
    }
    const value = fmt(metric.value, digits ?? 1);
    return suffix ? `${value}${suffix}` : value;
  }

  function latestMetric(data, name) {
    const metric = data.body && data.body.metrics ? data.body.metrics[name] : null;
    if (!metric || !metric.summary || !metric.summary.latest) return null;
    return metric.summary.latest;
  }

  function metricDelta(data, name) {
    const metric = data.body && data.body.metrics ? data.body.metrics[name] : null;
    if (!metric || !metric.summary) return null;
    return metric.summary.delta_from_first;
  }

  function weightLatest(data) {
    const official = data.weights && data.weights.summary ? data.weights.summary.official : null;
    if (official && official.latest) return official.latest;
    const all = data.weights && data.weights.summary ? data.weights.summary.all : null;
    return all && all.latest ? all.latest : null;
  }

  function weightDelta(data) {
    const official = data.weights && data.weights.summary ? data.weights.summary.official : null;
    if (official && official.delta_from_first !== null && official.delta_from_first !== undefined) return official.delta_from_first;
    const all = data.weights && data.weights.summary ? data.weights.summary.all : null;
    return all ? all.delta_from_first : null;
  }

  function card(title, value, suffix, delta, note) {
    return `
      <article class="w2-card">
        <span>${title}</span>
        <strong>${value}${suffix ? ` <small>${suffix}</small>` : ''}</strong>
        <small>${trendText(delta, suffix) || note || 'Sin tendencia suficiente'}</small>
      </article>
    `;
  }

  function renderCards(data) {
    const latestWeight = weightLatest(data);
    const cards = [];

    cards.push(card(
      'Peso oficial',
      latestWeight ? fmt(latestWeight.kg, 2) : '—',
      'kg',
      weightDelta(data),
      'Registra pesos oficiales para tendencia'
    ));

    [
      'body_fat_pct',
      'fat_mass_kg',
      'water_pct',
      'muscle_mass_kg',
      'visceral_fat',
      'bmr_kcal',
      'biocharge',
    ].forEach((name) => {
      const latest = latestMetric(data, name);
      cards.push(card(
        metricLabels[name] || name,
        latest ? fmt(latest.value, name === 'bmr_kcal' ? 0 : 1) : '—',
        unit(name),
        metricDelta(data, name),
        'Sin datos en rango'
      ));
    });

    document.getElementById('cards').innerHTML = cards.join('');
  }

  function renderInsights(data) {
    const insights = data.insights || [];
    document.getElementById('insights').innerHTML = insights.map((item) => `
      <article class="w2-insight ${item.level || 'neutral'}">
        <span>${typeLabel(item.type)}</span>
        <h3>${item.title || 'Insight'}</h3>
        <p>${item.message || ''}</p>
      </article>
    `).join('');
  }

  function bodyByDate(data) {
    const map = new Map();

    const weights = (data.weights && data.weights.items) || [];
    weights.forEach((w) => {
      const key = w.date;
      if (!map.has(key)) map.set(key, { date: key, time: '', weight: null, metrics: {} });
      const item = map.get(key);
      if (w.official || !item.weight) item.weight = w;
    });

    const snaps = (data.body && data.body.snapshots) || [];
    snaps.forEach((snap) => {
      const key = snap.date;
      if (!map.has(key)) map.set(key, { date: key, time: snap.time || '', weight: null, metrics: {} });
      const item = map.get(key);
      item.time = snap.time || item.time;
      Object.assign(item.metrics, snap.metrics || {});
    });

    return Array.from(map.values()).sort((a, b) => (a.date + a.time).localeCompare(b.date + b.time)).reverse();
  }

  function renderTable(data) {
    const rows = bodyByDate(data).slice(0, 40);
    document.getElementById('snapshots').innerHTML = rows.map((row) => `
      <tr>
        <td>${row.date}${row.time ? ` · ${row.time}` : ''}</td>
        <td>${row.weight ? `${fmt(row.weight.kg, 2)} kg${row.weight.official ? '' : ' ref.'}` : '—'}</td>
        <td>${metricCell(row, 'body_fat_pct', '%', 1)}</td>
        <td>${metricCell(row, 'water_pct', '%', 1)}</td>
        <td>${metricCell(row, 'muscle_mass_kg', ' kg', 1)}</td>
        <td>${metricCell(row, 'visceral_fat', '', 0)}</td>
        <td>${metricCell(row, 'bmr_kcal', '', 0)}</td>
        <td>${metricCell(row, 'biocharge', '', 0)}</td>
      </tr>
    `).join('');
  }

  function setActiveButton(days) {
    document.querySelectorAll('[data-days]').forEach((btn) => {
      btn.classList.toggle('is-active', String(days) === btn.getAttribute('data-days'));
    });
  }

  async function load(days) {
    currentDays = days || currentDays;
    setActiveButton(currentDays);

    const res = await fetch(`/api/body-trends?days=${encodeURIComponent(currentDays)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    if (data.status !== 'ok') throw new Error(data.error || 'API error');

    document.getElementById('rangeLabel').textContent = `${data.range.from} → ${data.range.to}`;
    renderInsights(data);
    renderCards(data);
    renderTable(data);
  }

  document.querySelectorAll('[data-days]').forEach((btn) => {
    btn.addEventListener('click', () => load(Number(btn.getAttribute('data-days')) || 30));
  });

  load(30).catch((err) => {
    document.getElementById('insights').innerHTML = `
      <article class="w2-insight bad">
        <span>Error</span>
        <h3>No se pudo cargar Peso 2.0</h3>
        <p>${err.message}</p>
      </article>
    `;
    console.error(err);
  });
})();
