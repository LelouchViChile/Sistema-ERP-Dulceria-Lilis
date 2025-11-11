// main.js — Búsqueda AJAX en vivo para formularios GET con [data-live="search"]
// Reemplaza: <tbody id="list-body"> y <nav id="list-pagination"> con el HTML recibido.

(function () {
  function log() { try { console.log.apply(console, arguments); } catch (_) {} }

  // Evita respuestas que llegan desordenadas
  let currentAbort = null;

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
      if (v !== null && v !== undefined && v !== "") params.append(k, v);
    }
    return params.toString();
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

    // Re-engancha paginación (links <a href="?page=2&...">)
    if (curPag) {
      curPag.querySelectorAll("a[href]").forEach(a => {
        a.addEventListener("click", function (ev) {
          ev.preventDefault();
          refreshFromURL(this.href);
        });
      });
    }
  }

  async function doFetch(url) {
    if (currentAbort) currentAbort.abort();
    currentAbort = new AbortController();

    const res = await fetch(url, {
      method: "GET",
      credentials: "same-origin",
      signal: currentAbort.signal
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.text();
  }

  async function refreshFromURL(full) {
    try {
      document.body.style.cursor = "progress";
      const html = await doFetch(full);
      extractAndSwap(html);
      window.history.replaceState({}, "", full);
    } catch (e) {
      log("[live-search] error:", e);
    } finally {
      document.body.style.cursor = "";
    }
  }

  function buildURLFromForm(form) {
    const url = form.action || window.location.pathname;
    const qs  = serializeForm(form);
    return qs ? `${url}?${qs}` : url;
  }

  function refreshFromForm(form) {
    const full = buildURLFromForm(form);
    return refreshFromURL(full);
  }

  function setupLiveSearch(root = document) {
    const form = root.querySelector('form[data-live="search"]');
    if (!form) return;

    // Submit (Enter / botón)
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      refreshFromForm(form);
    });

    const debounced = debounce(() => refreshFromForm(form), 250);

    // Dispara mientras escribes (incluye backspace)
    form.querySelectorAll("input[type='text'], input[type='search']").forEach(inp => {
      inp.addEventListener("input", debounced);
      inp.addEventListener("keyup", debounced);      // fallback para algunos navegadores
      inp.addEventListener("search", debounced);     // cuando tocan la “X” para limpiar
    });

    // Cambios en selects/checkbox/radio
    form.addEventListener("change", function (ev) {
      const el = ev.target;
      if (!el) return;
      if (el.tagName === "SELECT" || el.type === "checkbox" || el.type === "radio") {
        refreshFromForm(form);
      }
    });

    // Cargar la lista limpia cuando el q está vacío
    const q = form.querySelector("[name='q']");
    if (q && !q.value) refreshFromForm(form);
  }

  document.addEventListener("DOMContentLoaded", () => {
    setupLiveSearch(document);
    log("[live-search] listo");
  });
})();
