/*
 * Diet Pro Planner · tiny SVG chart kit (no dependencies, CSP friendly).
 * - timeChart(): daily columns / lines / dots on one y-axis, optional reference
 *   line or step series, crosshair + tooltip listing every series at that day.
 * - stackBar(): 100% horizontal bar with 2px gaps, legend and direct labels.
 * Colours follow the validated categorical order (blue, orange, aqua).
 */
(function () {
  'use strict';

  const NS = 'http://www.w3.org/2000/svg';
  const COLORS = {s1: '#2a78d6', s2: '#eb6834', s3: '#1baf7a', muted: '#9aa5b1', ref: '#52514e', grid: '#e6e9ee', text: '#52514e'};
  const nf = (v, d = 1) => Number(v).toLocaleString('es-ES', {maximumFractionDigits: d});

  function el(name, attrs, parent) {
    const node = document.createElementNS(NS, name);
    Object.entries(attrs || {}).forEach(([k, v]) => node.setAttribute(k, String(v)));
    if (parent) parent.appendChild(node);
    return node;
  }

  function niceTicks(min, max, count = 4) {
    if (!isFinite(min) || !isFinite(max)) return [0, 1];
    if (min === max) { min -= 1; max += 1; }
    const raw = (max - min) / count;
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) || raw;
    const ticks = [];
    for (let v = Math.floor(min / step) * step; v <= max + step * 0.001; v += step) ticks.push(Number(v.toFixed(6)));
    if (ticks[ticks.length - 1] < max) ticks.push(ticks[ticks.length - 1] + step);
    return ticks;
  }

  function shortDate(iso) {
    const d = new Date(`${iso}T12:00:00`);
    return d.toLocaleDateString('es-ES', {day: 'numeric', month: 'short'});
  }

  /**
   * opts: {dates, series: [{label, type: 'bar'|'line'|'dots', color, values, unit, digits}],
   *        ref: {value, label} | null, zeroBased, unit, height, ariaLabel}
   */
  function timeChart(container, opts) {
    const host = typeof container === 'string' ? document.querySelector(container) : container;
    if (!host) return;
    host.innerHTML = '';
    host.classList.add('dpp-chart');
    host.__dppChart = opts;
    const dates = opts.dates || [];
    // Real pixel width so 11px labels stay 11px on narrow cards and phones.
    const W = Math.max(300, Math.round(host.clientWidth || 760));
    const H = opts.height || (W < 520 ? 220 : 260), L = 46, R = 12, T = 16, B = 30;
    const pw = W - L - R, ph = H - T - B, n = Math.max(1, dates.length);
    const values = opts.series.flatMap((s) => s.values.filter((v) => v !== null && v !== undefined && isFinite(v)));
    if (opts.ref && isFinite(opts.ref.value)) values.push(opts.ref.value);
    if (!values.length) { host.innerHTML = '<div class="empty">Aún no hay datos en este rango.</div>'; return; }
    let min = Math.min(...values), max = Math.max(...values);
    if (opts.zeroBased) min = 0;
    else { const pad = (max - min) * 0.12 || 0.5; min -= pad; max += pad; }
    const ticks = niceTicks(min, max);
    const y0 = ticks[0], y1 = ticks[ticks.length - 1];
    const band = pw / n;
    const x = (i) => L + band * i + band / 2;
    const y = (v) => T + (y1 - v) / (y1 - y0) * ph;

    const svg = el('svg', {viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': opts.ariaLabel || 'Gráfico'}, host);
    ticks.forEach((t) => {
      el('line', {x1: L, x2: W - R, y1: y(t), y2: y(t), stroke: COLORS.grid, 'stroke-width': 1}, svg);
      el('text', {x: L - 8, y: y(t) + 4, 'text-anchor': 'end', 'font-size': 11, fill: COLORS.text, class: 'tick'}, svg).textContent = nf(t, opts.tickDigits ?? 1);
    });
    [0, Math.floor((n - 1) / 2), n - 1].filter((v, i, a) => a.indexOf(v) === i && dates[v]).forEach((i) => {
      const anchor = i === 0 ? 'start' : i === n - 1 ? 'end' : 'middle';
      el('text', {x: i === 0 ? L : i === n - 1 ? W - R : x(i), y: H - 8, 'text-anchor': anchor, 'font-size': 11, fill: COLORS.text}, svg).textContent = shortDate(dates[i]);
    });

    const barSeries = opts.series.filter((s) => s.type === 'bar');
    const barW = Math.max(2, Math.min(24, band - 2) / Math.max(1, barSeries.length));
    opts.series.forEach((s) => {
      const color = s.color || COLORS.s1;
      if (s.type === 'bar') {
        const offset = barSeries.indexOf(s) * barW - (barSeries.length * barW) / 2;
        s.values.forEach((v, i) => {
          if (v === null || v === undefined || !(v > 0)) return;
          const top = y(v), base = y(Math.max(0, y0)), h = Math.max(1, base - top), r = Math.min(4, barW / 2, h);
          const x0 = x(i) + offset, x1 = x0 + barW;
          // Rounded data end, square at the baseline.
          el('path', {d: `M${x0},${base} V${top + r} Q${x0},${top} ${x0 + r},${top} H${x1 - r} Q${x1},${top} ${x1},${top + r} V${base} Z`, fill: color}, svg);
        });
      } else if (s.type === 'line' || s.type === 'step') {
        let d = '', started = false;
        s.values.forEach((v, i) => {
          if (v === null || v === undefined || !isFinite(v)) { started = false; return; }
          if (s.type === 'step' && started) d += ` H${x(i) - band / 2} V${y(v)} H${x(i)}`;
          else d += `${started ? ' L' : ' M'}${x(i)},${y(v)}`;
          started = true;
        });
        el('path', {d: d.trim(), fill: 'none', stroke: color, 'stroke-width': s.width || 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round'}, svg);
        const lastIdx = s.values.map((v, i) => (v !== null && v !== undefined && isFinite(v) ? i : -1)).filter((i) => i >= 0).pop();
        if (s.endLabel && lastIdx !== undefined) {
          el('circle', {cx: x(lastIdx), cy: y(s.values[lastIdx]), r: 4, fill: color, stroke: '#fff', 'stroke-width': 2}, svg);
          el('text', {x: Math.min(x(lastIdx), W - R - 2), y: y(s.values[lastIdx]) - 9, 'text-anchor': 'end', 'font-size': 12, 'font-weight': 700, fill: '#0b1726'}, svg).textContent = `${nf(s.values[lastIdx], s.digits ?? 1)}${s.unit || ''}`;
        }
      } else if (s.type === 'dots') {
        s.values.forEach((v, i) => {
          if (v === null || v === undefined || !isFinite(v)) return;
          el('circle', {cx: x(i), cy: y(v), r: 3.5, fill: color, stroke: '#fff', 'stroke-width': 1.5}, svg);
        });
      }
    });

    if (opts.ref && isFinite(opts.ref.value)) {
      el('line', {x1: L, x2: W - R, y1: y(opts.ref.value), y2: y(opts.ref.value), stroke: COLORS.ref, 'stroke-width': 1.5}, svg);
      el('text', {x: L + 6, y: y(opts.ref.value) - 6, 'font-size': 11, 'font-weight': 700, fill: COLORS.ref}, svg).textContent = opts.ref.label;
    }

    // Crosshair + tooltip (values lead, labels follow; built with textContent).
    const cross = el('line', {y1: T, y2: T + ph, stroke: '#0b1726', 'stroke-width': 1, opacity: 0}, svg);
    const tip = document.createElement('div');
    tip.className = 'dpp-chart-tip'; tip.hidden = true; host.appendChild(tip);
    const hit = el('rect', {x: L, y: T, width: pw, height: ph, fill: 'transparent'}, svg);
    const show = (clientX) => {
      const box = svg.getBoundingClientRect();
      const px = (clientX - box.left) / box.width * W;
      const i = Math.max(0, Math.min(n - 1, Math.floor((px - L) / band)));
      cross.setAttribute('x1', x(i)); cross.setAttribute('x2', x(i)); cross.setAttribute('opacity', 0.35);
      tip.replaceChildren();
      const head = document.createElement('div'); head.className = 'dpp-chart-tip-date'; head.textContent = new Date(`${dates[i]}T12:00:00`).toLocaleDateString('es-ES', {weekday: 'short', day: 'numeric', month: 'short'}); tip.appendChild(head);
      opts.series.concat(opts.extraTooltip || []).forEach((s) => {
        const v = s.values[i];
        const row = document.createElement('div'); row.className = 'dpp-chart-tip-row';
        const key = document.createElement('i'); key.style.background = s.color || COLORS.muted; row.appendChild(key);
        const b = document.createElement('b'); b.textContent = v === null || v === undefined || !isFinite(v) ? '—' : `${nf(v, s.digits ?? 1)}${s.unit || ''}`; row.appendChild(b);
        const sm = document.createElement('span'); sm.textContent = s.label; row.appendChild(sm);
        tip.appendChild(row);
      });
      tip.hidden = false;
      const left = (x(i) / W) * box.width;
      tip.style.left = `${Math.min(Math.max(8, left + 12), box.width - tip.offsetWidth - 8)}px`;
    };
    hit.addEventListener('pointermove', (ev) => show(ev.clientX));
    hit.addEventListener('pointerdown', (ev) => show(ev.clientX));
    hit.addEventListener('pointerleave', () => { tip.hidden = true; cross.setAttribute('opacity', 0); });

    if (opts.series.length > 1 || opts.legend) {
      const legend = document.createElement('div'); legend.className = 'dpp-chart-legend';
      opts.series.forEach((s) => {
        const item = document.createElement('span');
        const key = document.createElement('i'); key.className = s.type === 'bar' ? 'bar' : s.type === 'dots' ? 'dot' : 'line'; key.style.background = s.color || COLORS.s1;
        item.appendChild(key); item.appendChild(document.createTextNode(s.label)); legend.appendChild(item);
      });
      if (opts.ref) { const item = document.createElement('span'); const key = document.createElement('i'); key.className = 'line'; key.style.background = COLORS.ref; item.appendChild(key); item.appendChild(document.createTextNode(opts.ref.label)); legend.appendChild(item); }
      host.insertBefore(legend, svg);
    }
  }

  /** segments: [{label, value, color, display}] -> 100% bar with direct labels when they fit. */
  function stackBar(container, segments) {
    const host = typeof container === 'string' ? document.querySelector(container) : container;
    if (!host) return;
    const total = segments.reduce((a, s) => a + Math.max(0, s.value), 0) || 1;
    const bar = document.createElement('div'); bar.className = 'dpp-stack';
    const legend = document.createElement('div'); legend.className = 'dpp-chart-legend';
    segments.forEach((s) => {
      const pct = Math.max(0, s.value) / total * 100;
      const seg = document.createElement('div'); seg.className = 'dpp-stack-seg'; seg.style.width = `${pct}%`; seg.style.background = s.color;
      seg.title = `${s.label}: ${s.display}`;
      if (pct >= 14) { const t = document.createElement('span'); t.textContent = `${Math.round(pct)}%`; seg.appendChild(t); }
      bar.appendChild(seg);
      const item = document.createElement('span'); const key = document.createElement('i'); key.className = 'bar'; key.style.background = s.color;
      item.appendChild(key); item.appendChild(document.createTextNode(`${s.label} · ${s.display}`)); legend.appendChild(item);
    });
    host.replaceChildren(bar, legend);
  }

  let resizeTimer = null;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      document.querySelectorAll('.dpp-chart').forEach((host) => { if (host.__dppChart && host.isConnected) timeChart(host, host.__dppChart); });
    }, 200);
  });

  window.DPPCharts = {timeChart, stackBar, COLORS, shortDate};
})();
