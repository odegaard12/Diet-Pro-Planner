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
      findTextElement("Inteligencia del día")?.closest("section, article, .card")
    );
  }

  function render(data) {
    const c = data.coach || {};
    const totals = c.totals || {};
    const next = c.next_meal || {};
    const messages = c.messages || {};
    const flags = c.flags || [];

    const hero = findHero();
    const panel = findPanel();

    if (!hero && !panel) return false;

    if (hero) {
      hero.dataset.dppCoachV17 = "1";

      const kicker = hero.querySelector(".fi13-kicker") || findTextElement("Inteligencia del día");
      if (kicker) kicker.textContent = "Coach del día · v0.0.17";

      const h2 = hero.querySelector("h2");
      if (h2) h2.textContent = c.headline || "Coach del día";

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

      const h3 = panel.querySelector("h3") || findTextElement("Qué hacer ahora");
      if (h3) h3.textContent = "Coach del día";

      const sub = panel.querySelector("header p");
      if (sub) {
        sub.textContent = `${totals.meals || 0} comidas · ${fmt(totals.kcal, " kcal")} · ${fmt(totals.protein, " g proteína")} · ${c.training_type || "sin_entreno"}`;
      }

      const btn =
        panel.querySelector("#fi13SuggestBtn") ||
        panel.querySelector("button");

      if (btn) {
        btn.textContent = "Actualizar coach";
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

      let ul = panel.querySelector("ul");
      if (!ul) {
        ul = document.createElement("ul");
        panel.appendChild(ul);
      }

      const items = [];
      if (next.primary) items.push(`<li><b>Siguiente mejor comida:</b> ${esc(next.primary)}</li>`);
      if (next.why) items.push(`<li>${esc(next.why)}</li>`);
      if (messages.protein) items.push(`<li>💪 ${esc(messages.protein)}</li>`);
      if (messages.biocharge) items.push(`<li>⚡ ${esc(messages.biocharge)}</li>`);
      if (messages.weight) items.push(`<li>⚖️ ${esc(messages.weight)}</li>`);
      if (messages.yesterday) items.push(`<li>🧠 ${esc(messages.yesterday)}</li>`);

      const avoid = Array.isArray(next.avoid) ? next.avoid.filter(Boolean) : [];
      if (avoid.length) items.push(`<li><b>Evitar ahora:</b> ${esc(avoid.join(", "))}</li>`);

      ul.innerHTML = items.length ? items.join("") : "<li>Registra comida real antes de valorar el día.</li>";

      const box = panel.querySelector("#fi13Suggestions");
      if (box) {
        box.innerHTML = flags.length
          ? `<div class="muted">Señales: ${flags.map(esc).join(" · ")}</div>`
          : "";
      }
    }

    const eyebrow = document.querySelector(".eyebrow");
    if (eyebrow && eyebrow.textContent.includes("v0.0.16")) {
      eyebrow.textContent = eyebrow.textContent.replace("v0.0.16", "v0.0.17");
    }

    return true;
  }

  async function loadCoach(force) {
    if (busy) return;
    const day = currentDay();
    const key = day + "|" + document.body.textContent.slice(0, 300);
    if (!force && key === lastAppliedKey) return;

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
        const h3 = panel.querySelector("h3");
        if (h3) h3.textContent = "Coach del día";
        let ul = panel.querySelector("ul");
        if (!ul) {
          ul = document.createElement("ul");
          panel.appendChild(ul);
        }
        ul.innerHTML = `<li>No se pudo cargar Smart Coach: ${esc(err.message || err)}</li>`;
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

  // Reintentos iniciales porque la app antigua pinta después de cargar datos.
  [300, 800, 1500, 3000].forEach((ms) => setTimeout(() => schedule(true), ms));
})();
