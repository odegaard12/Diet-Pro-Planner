/* Diet Pro Planner v0.0.19 · candidate polish */
(function () {
  'use strict';

  const VERSION = 'v0.0.19';
  let excludedProteins = [];
  let currentUsed = [];

  function syncVersion() {
    const title = `Diet Pro Planner · ${VERSION}`;
    const eyebrowText = `Dieta controlada · ${VERSION}`;
    if (document.title !== title) document.title = title;

    const eyebrow = document.querySelector('.eyebrow');
    if (eyebrow && eyebrow.textContent.trim() !== eyebrowText) eyebrow.textContent = eyebrowText;

    const badge = document.querySelector('#ui5Badge');
    if (badge && badge.textContent.trim() !== VERSION) badge.textContent = VERSION;

    document.querySelectorAll('.topbar *, [class*="version"], [data-version]').forEach((node) => {
      if (node.children.length) return;
      const text = String(node.textContent || '').trim();
      if (/^v0\.0\.18(?:\b|$)/.test(text)) node.textContent = VERSION;
    });
  }

  function selectedDay() {
    const input = document.querySelector('#dashDate');
    return input?.value || new Date().toISOString().slice(0, 10);
  }

  async function requestJson(url, options) {
    const response = await fetch(url, {
      credentials: 'same-origin',
      headers: {'Content-Type': 'application/json'},
      ...(options || {})
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    return payload;
  }

  async function getCurrentUsed() {
    if (currentUsed.length) return currentUsed;
    const result = await requestJson(`/api/smart-coach/day?date=${encodeURIComponent(selectedDay())}`);
    currentUsed = result.coach?.pantry?.used || [];
    return currentUsed;
  }

  function applyAlternative(result) {
    const alternative = result.alternative || {};
    if (!alternative.primary) throw new Error('La alternativa no contiene una comida válida');
    currentUsed = Array.isArray(alternative.pantry_used) ? alternative.pantry_used : [];

    const decision = document.querySelector('.dpp-coach-decision');
    const why = document.querySelector('.dpp-coach-why');
    const heroText = document.querySelector('.fi13-hero p');
    if (decision) decision.textContent = alternative.primary;
    if (why) why.textContent = alternative.why || '';
    if (heroText) heroText.textContent = alternative.primary;
    document.querySelector('#coachUnavailablePicker')?.remove();
  }

  window.coachAnotherMeal = async function () {
    try {
      const used = await getCurrentUsed();
      const mainProtein = used[0];
      if (mainProtein && !excludedProteins.includes(mainProtein)) excludedProteins.push(mainProtein);

      let result;
      try {
        result = await requestJson('/api/smart-coach/alternative', {
          method: 'POST',
          body: JSON.stringify({date: selectedDay(), exclude: excludedProteins, offset: 0})
        });
      } catch (error) {
        excludedProteins = mainProtein ? [mainProtein] : [];
        result = await requestJson('/api/smart-coach/alternative', {
          method: 'POST',
          body: JSON.stringify({date: selectedDay(), exclude: excludedProteins, offset: 0})
        });
      }

      applyAlternative(result);
      if (typeof toast === 'function') toast('Nueva comida completa preparada');
    } catch (error) {
      if (typeof toast === 'function') toast(`Coach: ${error.message}`);
    }
  };

  const observer = new MutationObserver(syncVersion);
  observer.observe(document.documentElement, {childList: true, characterData: true, subtree: true});
  syncVersion();
  setInterval(syncVersion, 500);
})();
