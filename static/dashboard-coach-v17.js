(function () {
  const ENDPOINT = "/api/smart-coach/day";

  function todayLocal() {
    const d = new Date();
    d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
    return d.toISOString().slice(0, 10);
  }

  function currentDay() {
    const dateInput = document.querySelector("#dashDate") || document.querySelector("input[type='date']");
    return dateInput && dateInput.value ? dateInput.value : todayLocal();
  }

  function txt(v) {
    return v === null || v === undefined ? "" : String(v);
  }

  function fmt(n, suffix) {
    const x = Number(n || 0);
    const clean = Math.round(x * 10) / 10;
    return `${clean}${suffix || ""}`;
  }

  function findTextElement(needle) {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = walker.nextNode())) {
      if (n.nodeValue && n.nodeValue.includes(needle)) return n.parentElement;
    }
    return null;
  }

  function blockContaining(needles) {
    const seed = findTextElement(needles[0]);
    if (!seed) return null;

    let cur = seed;
    for (let i = 0; i < 8 && cur && cur.parentElement; i++) {
      const s = cur.textContent || "";
      if (needles.every((x) => s.includes(x))) return cur;
      cur = cur.parentElement;
    }
    return seed.closest("section, article, .card") || seed.parentElement;
  }

  function listItem(text) {
    return `<li>${escapeHtml(text)}</li>`;
  }

  function escapeHtml(s) {
    return txt(s)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function ensureRefreshButton(panel) {
    let btn = panel.querySelector("[data-dpp-coach-refresh]");
    const oldSuggest = panel.querySelector("#fi13SuggestBtn");

    if (oldSuggest) {
      oldSuggest.id = "";
      oldSuggest.dataset.dppCoachRefresh = "1";
      oldSuggest.textContent = "Actualizar coach";
      oldSuggest.onclick = null;
      btn = oldSuggest;
    }

    if (!btn) {
      const header = panel.querySelector("header");
      if (header) {
        btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn small";
        btn.dataset.dppCoachRefresh = "1";
        btn.textContent = "Actualizar coach";
        header.appendChild(btn);
      }
    }

    if (btn && !btn.dataset.boundCoach) {
      btn.dataset.boundCoach = "1";
      btn.addEventListener("click", function (ev) {
        ev.preventDefault();
        loadCoach();
      });
    }
  }

  function renderCoach(data) {
    const c = data.coach || {};
    const totals = c.totals || {};
    const next = c.next_meal || {};
    const messages = c.messages || {};
    const flags = c.flags || [];

    const hero = document.querySelector(".fi13-hero");
    if (hero) {
      hero.dataset.dppCoachV17 = "1";

      const kicker = hero.querySelector(".fi13-kicker");
      if (kicker) kicker.textContent = "Coach del día · v0.0.17";

      const h2 = hero.querySelector("h2");
      if (h2) h2.textContent = c.headline || "Coach del día";

      const p = hero.querySelector("p");
      if (p) p.textContent = next.primary || "Registra comida real para calcular mejor.";

      const tags = hero.querySelector(".fi13-hero-tags");
      if (tags) {
        tags.innerHTML = `
          <span>${escapeHtml(totals.meals || 0)} comidas</span>
          <span>${escapeHtml(fmt(totals.kcal, " kcal"))}</span>
          <span>${escapeHtml(fmt(totals.protein, " g proteína"))}</span>
          <span>${escapeHtml(fmt(totals.workout_kcal, " kcal entreno"))}</span>
        `;
      }
    }

    const panel = document.querySelector(".fi13-next") || blockContaining(["Qué hacer ahora"]);
    if (!panel) return;

    panel.dataset.dppCoachV17 = "1";

    const h3 = panel.querySelector("h3");
    if (h3) h3.textContent = "Coach del día";

    const sub = panel.querySelector("header p");
    if (sub) {
      sub.textContent = `${totals.meals || 0} comidas · ${fmt(totals.kcal, " kcal")} · ${fmt(totals.protein, " g proteína")} · ${c.training_type || "sin_entreno"}`;
    }

    ensureRefreshButton(panel);

    const ul = panel.querySelector("ul") || document.createElement("ul");
    if (!ul.parentElement) panel.appendChild(ul);

    const items = [];

    if (next.primary) items.push(`Siguiente mejor comida: ${next.primary}`);
    if (next.why) items.push(next.why);
    if (messages.protein) items.push(messages.protein);
    if (messages.biocharge) items.push(messages.biocharge);
    if (messages.weight) items.push(messages.weight);
    if (messages.yesterday) items.push(messages.yesterday);

    const avoid = Array.isArray(next.avoid) ? next.avoid.filter(Boolean) : [];
    if (avoid.length) items.push(`Evitar ahora: ${avoid.join(", ")}.`);

    if (!items.length) items.push("Registra comida real antes de valorar el día.");

    ul.innerHTML = items.map(listItem).join("");

    const suggestions = panel.querySelector("#fi13Suggestions");
    if (suggestions) {
      suggestions.innerHTML = flags.length
        ? `<div class="muted">Señales: ${flags.map(escapeHtml).join(" · ")}</div>`
        : "";
    }

    const oldSuggestionTitle = findTextElement("Sugerir comida");
    if (oldSuggestionTitle && oldSuggestionTitle.textContent.trim() === "Sugerir comida") {
      oldSuggestionTitle.textContent = "Recomendación";
    }

    const eyebrow = document.querySelector(".eyebrow");
    if (eyebrow && eyebrow.textContent.includes("v0.0.16")) {
      eyebrow.textContent = eyebrow.textContent.replace("v0.0.16", "v0.0.17");
    }
  }

  async function loadCoach() {
    const day = currentDay();
    try {
      const res = await fetch(`${ENDPOINT}?date=${encodeURIComponent(day)}`, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      renderCoach(data);
    } catch (err) {
      const panel = document.querySelector(".fi13-next") || blockContaining(["Qué hacer ahora"]);
      if (panel) {
        const h3 = panel.querySelector("h3");
        if (h3) h3.textContent = "Coach del día";
        const ul = panel.querySelector("ul") || document.createElement("ul");
        if (!ul.parentElement) panel.appendChild(ul);
        ul.innerHTML = `<li>No se pudo cargar Smart Coach: ${escapeHtml(err.message || err)}</li>`;
      }
    }
  }

  function scheduleLoad() {
    window.clearTimeout(window.__dppCoachV17Timer);
    window.__dppCoachV17Timer = window.setTimeout(loadCoach, 350);
  }

  window.DPPCoachV17 = { load: loadCoach };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", scheduleLoad);
  } else {
    scheduleLoad();
  }

  document.addEventListener("change", function (ev) {
    if (ev.target && ev.target.matches("input[type='date'], #dashDate")) scheduleLoad();
  });

  document.addEventListener("click", function (ev) {
    const t = ev.target;
    if (t && (t.matches("button") || t.matches("a"))) scheduleLoad();
  });
})();
