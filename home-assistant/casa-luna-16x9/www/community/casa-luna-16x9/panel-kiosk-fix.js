/**
 * Panel kiosk layout fix — zeroes HA sidebar/drawer width on wall tablets.
 * Complements HACS kiosk-mode when sidebar content is hidden but layout space remains
 * (common on iPad / HA 2026 wa-drawer + sidebar-shell).
 *
 * Runs for non-admin users or on G-UNIT / Floorplan paths.
 */
(function () {
  "use strict";

  const STYLE_ID = "panel-kiosk-fix";
  const PANEL_PATHS = ["/casa-luna", "/g-unit-16x9", "/floorplan-4-3"];

  const ROOT_CSS = `
    :host {
      --ha-sidebar-width: 0px !important;
      --mdc-drawer-width: 0px !important;
      --kiosk-sidebar-width: 0px !important;
    }
    partial-panel-resolver {
      --mdc-top-app-bar-width: 100% !important;
    }
    ha-drawer,
    wa-drawer {
      --ha-sidebar-width: 0px !important;
      --mdc-drawer-width: 0px !important;
    }
    .sidebar-shell,
    ha-sidebar {
      display: none !important;
      width: 0 !important;
      min-width: 0 !important;
      max-width: 0 !important;
      visibility: hidden !important;
      pointer-events: none !important;
      overflow: hidden !important;
    }
    hui-panel-view,
    #view,
    hui-view {
      height: 100% !important;
      min-height: 100vh !important;
      padding: 0 !important;
      margin: 0 !important;
      overflow: hidden !important;
    }
  `;

  const DRAWER_CSS = `
    aside,
    .mdc-drawer,
    .mdc-drawer--open,
    .mdc-drawer--modal {
      width: 0 !important;
      min-width: 0 !important;
      max-width: 0 !important;
      display: none !important;
    }
    .mdc-drawer-app-content,
    .main-content,
    slot[name="panel"] {
      margin-left: 0 !important;
      padding-left: 0 !important;
      width: 100% !important;
    }
  `;

  function onPanelPath() {
    const path = window.location.pathname;
    return PANEL_PATHS.some((prefix) => path.includes(prefix));
  }

  function shouldRun(hass) {
    if (onPanelPath()) return true;
    const user = hass && hass.user;
    return Boolean(user && !user.is_admin);
  }

  function injectStyle(root, css, id) {
    if (!root) return;
    let style = root.getElementById ? root.getElementById(id) : null;
    if (!style) {
      style = document.createElement("style");
      style.id = id;
      if (root.getElementById) {
        root.appendChild(style);
      } else {
        return;
      }
    }
    style.textContent = css;
  }

  function zeroElement(el) {
    if (!el) return;
    el.style.setProperty("display", "none", "important");
    el.style.setProperty("width", "0", "important");
    el.style.setProperty("min-width", "0", "important");
    el.style.setProperty("max-width", "0", "important");
    el.style.setProperty("margin", "0", "important");
    el.style.setProperty("padding", "0", "important");
  }

  function fixLegacyDrawer(drawer) {
    if (!drawer || !drawer.shadowRoot) return;
    injectStyle(drawer.shadowRoot, DRAWER_CSS, STYLE_ID + "-legacy-drawer");
    zeroElement(drawer.shadowRoot.querySelector("aside"));
    zeroElement(drawer.shadowRoot.querySelector(".mdc-drawer"));
    zeroElement(drawer.shadowRoot.querySelector("ha-sidebar"));
    const content = drawer.shadowRoot.querySelector(".mdc-drawer-app-content");
    if (content) {
      content.style.setProperty("margin-left", "0", "important");
      content.style.setProperty("padding-left", "0", "important");
      content.style.setProperty("width", "100%", "important");
    }
  }

  function fixWaDrawer(drawer) {
    if (!drawer) return;
    if (drawer.shadowRoot) {
      injectStyle(drawer.shadowRoot, DRAWER_CSS, STYLE_ID + "-wa-drawer");
    }
    zeroElement(drawer.querySelector(".sidebar-shell"));
    zeroElement(drawer.querySelector("ha-sidebar"));
  }

  function apply(hass) {
    if (!shouldRun(hass)) return;

    const ha = document.querySelector("home-assistant");
    const haMain = ha && ha.shadowRoot && ha.shadowRoot.querySelector("home-assistant-main");
    if (!haMain || !haMain.shadowRoot) return;

    injectStyle(haMain.shadowRoot, ROOT_CSS, STYLE_ID + "-main");

    const root = haMain.shadowRoot;
    zeroElement(root.querySelector(".sidebar-shell"));
    zeroElement(root.querySelector("ha-sidebar"));

    root.querySelectorAll("ha-drawer").forEach(fixLegacyDrawer);
    root.querySelectorAll("wa-drawer").forEach(fixWaDrawer);

    const resolver = root.querySelector("partial-panel-resolver");
    if (resolver) {
      injectStyle(resolver, ROOT_CSS, STYLE_ID + "-resolver");
      zeroElement(resolver.querySelector(".sidebar-shell"));
      resolver.querySelectorAll("ha-drawer, wa-drawer").forEach((drawer) => {
        if (drawer.tagName === "HA-DRAWER") fixLegacyDrawer(drawer);
        else fixWaDrawer(drawer);
      });
    }
  }

  function waitForHass(callback) {
    const tick = () => {
      const ha = document.querySelector("home-assistant");
      if (ha && ha.hass) {
        callback(ha.hass);
        return;
      }
      requestAnimationFrame(tick);
    };
    tick();
  }

  function start() {
    waitForHass((hass) => {
      apply(hass);

      let lastPath = window.location.pathname;
      const reapply = () => {
        window.setTimeout(() => apply(hass), 50);
      };

      new MutationObserver(() => {
        if (window.location.pathname !== lastPath) {
          lastPath = window.location.pathname;
          reapply();
        }
      }).observe(document.body, { childList: true, subtree: true });

      window.addEventListener("resize", reapply);
      window.addEventListener("location-changed", reapply);
      window.addEventListener("hass-toggle-menu", reapply);

      let passes = 0;
      const interval = window.setInterval(() => {
        apply(hass);
        passes += 1;
        if (passes >= 30) window.clearInterval(interval);
      }, 500);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
