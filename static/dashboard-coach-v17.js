(function () {
  const ENDPOINT = "/api/smart-coach/day";
  let lastAppliedKey = "";
  let busy = false;
  let timer = null;

  function todayLocal() {
    const d = new Date();
    d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
    return d.toISOString().slice(0, 10);
  }

  function currentDay() {
    const dateInput = document.querySelector("#dashDate") || document.querySelector("input[type='date']");
    return dateInput && dateInput.value ? dateInput.value : todayLocal();
  }

  function esc(v) {
    return String(v ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function fmt(n, suffix) {
    const x = Number(n || 0);
    return `${Math.round(x * 10) / 10}${suffix || ""}`;
  }

  function findTextElement(needle) {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = walker.nextNode())) {
      if (n.nodeValue && n.nodeValue.includes(needle)) return n.parentElement;
    }
    return null;
  }

  function findPanel() {
    return (
      document.querySelector(".fi13-next") ||
      findTextElement("Qué hacer ahora")?.closest("article, section, .card") ||
      findTextElement("Sugerir comida")?.closest("article, section, .card")
    );
  }

  function findHero() {
    return (
      document.querySelector(".fi13-hero") ||
      findTextElement("Inteligencia del día")?.closest("section, article, .card") ||
      findTextElement("Coach del día")?.closest("section, article, .card")
    );
  }

  function chip(label, value) {
    return `<span class="dpp-coach-chip"><b>${esc(value)}</b><small>${esc(label)}</small></span>`;
  }

  function render(data) {
    const c = data.coach || {};
    const totals = c.totals || {};
    const next = c.next_meal || {};
    const messages = c.messages || {};
    const pantry = c.pantry || {};
    const flags = c.flags || [];

    const hero = findHero();
    const panel = findPanel();

    if (!hero && !panel) return false;

    if (hero) {
      hero.dataset.dppCoachV17 = "1";

      const kicker = hero.querySelector(".fi13-kicker") || findTextElement("Inteligencia del día");
      if (kicker) kicker.textContent = "Coach del día · v0.0.20";

      const h2 = hero.querySelector("h2");
      if (h2) h2.textContent = c.status === "base_insuficiente" ? "Aún no hay score, pero sí hay decisión" : (c.headline || "Coach del día");

      const p = hero.querySelector("p");
      if (p) p.textContent = next.primary || "Registra comida real para calcular mejor.";

      const tags = hero.querySelector(".fi13-hero-tags");
      if (tags) {
        tags.innerHTML = `
          <span>${esc(totals.meals || 0)} comidas</span>
          <span>${esc(fmt(totals.kcal, " kcal"))}</span>
          <span>${esc(fmt(totals.protein, " g proteína"))}</span>
          <span>${esc(fmt(totals.workout_kcal, " kcal entreno"))}</span>
        `;
      }
    }

    if (panel) {
      panel.dataset.dppCoachV17 = "1";
      panel.classList.add("dpp-coach-panel-v17");

      const h3 = panel.querySelector("h3") || findTextElement("Qué hacer ahora");
      if (h3) h3.textContent = "Coach del día";

      const sub = panel.querySelector("header p");
      if (sub) {
        sub.textContent = `${totals.meals || 0} comidas · ${fmt(totals.kcal, " kcal")} · ${fmt(totals.protein, " g proteína")} · ${c.training_type || "sin_entreno"}`;
      }

      const btn = panel.querySelector("#fi13SuggestBtn") || panel.querySelector("button");
      if (btn) {
        btn.textContent = "Actualizar";
        btn.removeAttribute("id");
        btn.onclick = null;
        if (!btn.dataset.dppCoachBound) {
          btn.dataset.dppCoachBound = "1";
          btn.addEventListener("click", function (ev) {
            ev.preventDefault();
            lastAppliedKey = "";
            loadCoach(true);
          });
        }
      }

      // Idempotente: antes de pintar, elimina cualquier Coach anterior dentro del panel.
      panel.querySelectorAll(".dpp-coach-visual, [data-dpp-coach-holder='1']").forEach((node) => node.remove());
      panel.querySelectorAll("ul").forEach((node) => node.remove());

      const holder = document.createElement("div");
      holder.dataset.dppCoachHolder = "1";
      panel.appendChild(holder);

      const used = Array.isArray(pantry.used) ? pantry.used : [];
      const avoid = Array.isArray(next.avoid) ? next.avoid.filter(Boolean) : [];

      holder.innerHTML = `
        <div class="dpp-coach-visual">
          <div class="dpp-coach-main">
            <div class="dpp-coach-label">MEJOR COMIDA AHORA</div>
            <div class="dpp-coach-decision">${esc(next.primary || "Registra comida real para calcular mejor.")}</div>
            <div class="dpp-coach-why">${esc(next.why || c.headline || "")}</div>
          </div>

          <div class="dpp-coach-grid">
            <div class="dpp-coach-box">
              <span>💪</span>
              <b>Proteína</b>
              <small>${esc(messages.protein || "Prioriza proteína útil.")}</small>
            </div>
            <div class="dpp-coach-box">
              <span>⚡</span>
              <b>Recuperación</b>
              <small>${esc(messages.biocharge || "BioCharge no disponible.")}</small>
            </div>
            <div class="dpp-coach-box">
              <span>🧠</span>
              <b>Contexto</b>
              <small>${esc(messages.yesterday || "Sin señales fuertes de ayer.")}</small>
            </div>
          </div>

          <div class="dpp-coach-row">
            ${chip("kcal", fmt(totals.kcal, ""))}
            ${chip("proteína", fmt(totals.protein, " g"))}
            ${chip("entreno", fmt(totals.workout_kcal, " kcal"))}
            ${chip("despensa", used.length ? used.join(" · ") : "sin datos")}
          </div>

          ${avoid.length ? `<div class="dpp-coach-avoid"><b>Evita ahora:</b> ${esc(avoid.join(" · "))}</div>` : ""}
          ${flags.length ? `<div class="dpp-coach-signals">Señales: ${flags.map(esc).join(" · ")}</div>` : ""}
        </div>
      `;

      const box = panel.querySelector("#fi13Suggestions");
      if (box) box.innerHTML = "";
    }

    const eyebrow = document.querySelector(".eyebrow");
    if (eyebrow && eyebrow.textContent.includes("v0.0.16")) {
      eyebrow.textContent = eyebrow.textContent.replace("v0.0.16", "v0.0.20");
    }

    return true;
  }

  async function loadCoach(force) {
    if (busy) return;
    const day = currentDay();
    const key = day;
    if (!force && key === lastAppliedKey && document.querySelector(".dpp-coach-visual")) return;

    const hero = findHero();
    const panel = findPanel();
    if (!hero && !panel) return;

    busy = true;
    try {
      const res = await fetch(`${ENDPOINT}?date=${encodeURIComponent(day)}`, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const ok = render(data);
      if (ok) lastAppliedKey = key;
    } catch (err) {
      const panel = findPanel();
      if (panel) {
        panel.dataset.dppCoachV17 = "1";
        panel.innerHTML += `<div class="dpp-coach-avoid">No se pudo cargar Smart Coach: ${esc(err.message || err)}</div>`;
      }
    } finally {
      busy = false;
    }
  }

  function schedule(force) {
    clearTimeout(timer);
    timer = setTimeout(() => loadCoach(force), 250);
  }

  window.DPPCoachV17 = {
    load: () => {
      lastAppliedKey = "";
      return loadCoach(true);
    }
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => schedule(true));
  } else {
    schedule(true);
  }

  const observer = new MutationObserver(() => schedule(false));
  observer.observe(document.documentElement, { childList: true, subtree: true });

  document.addEventListener("change", function (ev) {
    if (ev.target && ev.target.matches("input[type='date'], #dashDate")) {
      lastAppliedKey = "";
      schedule(true);
    }
  });

  document.addEventListener("click", function () {
    schedule(false);
  });

  [300, 800, 1500, 3000].forEach((ms) => setTimeout(() => schedule(true), ms));
})();
