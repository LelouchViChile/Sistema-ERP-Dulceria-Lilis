// main.js — Búsqueda AJAX en vivo para formularios GET con [data-live="search"]
// Reemplaza: <tbody id="list-body"> y <nav id="list-pagination"> con el HTML recibido.
// Soporta: tecleo (debounced), Enter/submit, cambio de <select>, clicks de paginación y redirección a login.

(function () {
  function log() { try { console.log.apply(console, arguments); } catch (_) {} }

  function debounce(fn, wait) {
    let t; return function (...args) { clearTimeout(t); t = setTimeout(() => fn.apply(this, args), wait); };
  }

  function serializeForm(form) {
    const fd = new FormData(form);
    const params = new URLSearchParams();
    for (const [k, v] of fd.entries()) {
      if (v !== null && v !== undefined && v !== '') params.append(k, v);
    }
    return params;
  }

  function extractAndSwap(htmlText) {
    const dom = document.createElement("html");
    dom.innerHTML = htmlText;

    const newBody = dom.querySelector("#list-body");
    const newPag  = dom.querySelector("#list-pagination");

    const curBody = document.querySelector("#list-body");
    const curPag  = document.querySelector("#list-pagination");

    if (newBody && curBody) curBody.innerHTML = newBody.innerHTML;
    if (newPag && curPag)   curPag.innerHTML  = newPag.innerHTML;

    // Re-engancha paginación cada vez que reemplazamos el HTML
    wirePagination();
  }

  async function doFetch(url, opts = {}) {
    const res = await fetch(url, { method: "GET", credentials: "same-origin", redirect: "follow", ...opts });
    const text = await res.text();
    return { ok: res.ok, status: res.status, text, finalUrl: res.url };
  }

  function ensureAbsolute(urlLike) {
    // Convierte acción relativa a absoluta en el mismo origen
    try { return new URL(urlLike, window.location.origin); }
    catch { return new URL(window.location.href); }
  }

  async function refreshFromForm(form) {
    const base = ensureAbsolute(form.action || window.location.pathname);
    const params = serializeForm(form);
    base.search = params.toString();

    try {
      document.body.style.cursor = "progress";
      const { ok, status, text, finalUrl } = await doFetch(base.toString());

      // Si nos mandaron al login, redirige la página completa para mantener la sesión coherente
      if (finalUrl.includes("/login/")) {
        window.location.href = finalUrl;
        return;
      }

      if (!ok) throw new Error(`HTTP ${status}`);
      extractAndSwap(text);

      // Actualiza la URL sin recargar
      window.history.replaceState({}, "", base.toString());
    } catch (e) {
      log("[live-search] error:", e);
    } finally {
      document.body.style.cursor = "";
    }
  }

  function wirePagination() {
    const nav = document.querySelector("#list-pagination");
    if (!nav) return;
    nav.querySelectorAll("a[href]").forEach(a => {
      a.addEventListener("click", ev => {
        ev.preventDefault();
        const form = document.querySelector('form[data-live="search"]');
        if (!form) { window.location.href = a.href; return; }
        // Usa la URL de la página que pidió el link
        const url = new URL(a.href, window.location.origin);
        // Conserva también los parámetros del form actual (por si hay filtros)
        const params = serializeForm(form);
        url.search = new URLSearchParams({ ...Object.fromEntries(url.searchParams), ...Object.fromEntries(params) }).toString();
        doFetch(url.toString()).then(({ finalUrl, ok, text }) => {
          if (finalUrl.includes("/login/")) { window.location.href = finalUrl; return; }
          if (!ok) return;
          extractAndSwap(text);
          window.history.replaceState({}, "", url.toString());
        }).catch(err => log("[live-search] paginación error:", err));
      }, { passive: false });
    });
  }

  function setupLiveSearch(root = document) {
    const form = root.querySelector('form[data-live="search"]');
    if (!form) { log("[live-search] No se encontró form[data-live='search']"); return; }

    // Submit (Enter / botón)
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      refreshFromForm(form);
    });

    // Tecleo (debounced)
    const debounced = debounce(() => refreshFromForm(form), 300);
    form.querySelectorAll("input[type='text'], input[type='search']").forEach(inp => {
      inp.addEventListener("input", debounced);
    });

    // Cambios en selects / checkboxes / radios
    form.addEventListener("change", function (ev) {
      const el = ev.target;
      if (!el) return;
      const tag = el.tagName;
      const type = (el.type || "").toLowerCase();
      if (tag === "SELECT" || type === "checkbox" || type === "radio") {
        refreshFromForm(form);
      }
    });

    wirePagination();
  }

  document.addEventListener("DOMContentLoaded", () => {
    setupLiveSearch(document);
    log("[live-search] listo");
  });
})();
