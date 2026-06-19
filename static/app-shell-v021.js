/* Diet Pro Planner v0.0.21 · Modern App Shell */
(function () {
  'use strict';

  if (window.__DPP_APP_SHELL_V021__) return;
  window.__DPP_APP_SHELL_V021__ = true;

  const VERSION = 'v0.0.21-dev';

  function syncVersion() {
    document.title = `Diet Pro Planner · ${VERSION}`;

    const eyebrow = document.querySelector('.eyebrow');
    if (eyebrow) {
      eyebrow.textContent = `Dieta controlada · ${VERSION}`;
    }

    const badge = document.querySelector('#ui5Badge');
    if (badge) {
      badge.textContent = VERSION;
    }
  }

  function modernizeShell() {
    document.body.classList.add('dpp-modern-shell');

    const sidebar = document.querySelector('.sidebar');
    if (sidebar) {
      sidebar.setAttribute('aria-label', 'Navegación principal');
    }

    const main = document.querySelector('.main');
    if (main) {
      main.setAttribute('role', 'main');
    }

    syncVersion();
  }

  try {
    if (typeof render === 'function' && !render.__dppShellV021) {
      const previousRender = render;

      const wrappedRender = function () {
        const result = previousRender.apply(this, arguments);
        requestAnimationFrame(modernizeShell);
        return result;
      };

      wrappedRender.__dppShellV021 = true;
      window.render = wrappedRender;
      render = wrappedRender;
    }
  } catch (error) {
    console.warn('DPP v0.0.21 shell wrapper:', error);
  }

  document.addEventListener('click', function () {
    requestAnimationFrame(modernizeShell);
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', modernizeShell, {
      once: true
    });
  } else {
    modernizeShell();
  }
})();
