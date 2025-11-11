// main.js — Búsqueda AJAX en vivo para formularios GET con [data-live="search"]
// Reemplaza: <tbody id="list-body"> y <nav id="list-pagination"> con el HTML recibido.
// Soporta: tecleo (debounced), Enter/submit, cambio de <select>, y clicks de paginación.

(function () {
  function log() { try { console.log.apply(console, arguments); } catch (_) {} }

  function debounce(fn, wait) {
    let t;
    return function (...args) {
      clearTimeout(t);
      t = setTimeout(() => fn.apply(this, args), wait);
    };
  }

  function serializeForm(form) {
    const fd = new FormData(form);
    const params = new URLSearchParams();
    for (const [k, v] of fd.entries()) {
      // Evita parámetros vacíos inútiles
      if (v !== null && v !== undefined && v !== '') params.append(k, v);
    }
    return params.toString();
  }

  function extractAndSwap(htmlText) {
    // Crea un DOM temporal para buscar los nuevos #list-body y #list-pagination
    const dom = document.createElement("html");
    dom.innerHTML = htmlText;

    const newBody = dom.querySelector("#list-body");
    const newPag  = dom.querySelector("#list-pagination");

    const curBody = document.querySelector("#list-body");
    const curPag  = document.querySelector("#list-pagination");

    if (newBody && curBody) {
      curBody.innerHTML = newBody.innerHTML;
    }
    if (newPag && curPag) {
      curPag.innerHTML = newPag.innerHTML;
    }
  }

  async function doFetch(url, opts = {}) {
    const res = await fetch(url, { method: "GET", credentials: "same-origin", ...opts });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.text();
  }

  async function refreshFromForm(form) {
    const url = form.action || window.location.pathname;
    const qs  = serializeForm(form);
    const full = qs ? `${url}?${qs}` : url;
    try {
      document.body.style.cursor = "progress";
      const html = await doFetch(full);
      extractAndSwap(html);
      window.history.replaceState({}, "", full); // Actualiza la URL (sin recargar)
    } catch (e) {
      log("[live-search] error:", e);
    } finally {
      document.body.style.cursor = "";
    }
  }

  // ===== wire-up =====
  function setupLiveSearch(root = document) {
    const form = root.querySelector('form[data-live="search"]');
    if (!form) return;

    // 1) Submit (Enter o click en la “lupa”)
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      refreshFromForm(form);
    });

    // 2) Tecleo en inputs (debounced)
    const debounced = debounce(() => refreshFromForm(form), 300);
    form.querySelectorAll("input[type='text'], input[type='search']").forEach(inp => {
      inp.addEventListener("input", debounced);
    });

    // 3) Cambios en selects/radios, etc.
    form.addEventListener("change", function (ev) {
      const el = ev.target;
      if (el && (el.tagName === "SELECT" || el.type === "checkbox" || el.type === "radio")) {
        refreshFromForm(form);
      }
    });
  }

  // Inicializa
  document.addEventListener("DOMContentLoaded", () => {
    setupLiveSearch(document);
    log("[live-search] listo");
  });
})();