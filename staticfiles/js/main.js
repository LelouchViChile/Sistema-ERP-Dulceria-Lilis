// static/js/live-search.js
// Live search unificado (input debounced + submit + paginación) sin recarga.
// - Escribir/borrar en <input name="q">: filtra y si está vacío vuelve al listado inicial.
// - Submit del form (orden/otros filtros): AJAX.
// - Paginación: AJAX.
// - Reatacha eventos tras cada swap (no se muere el input).
// Requisitos de HTML por página de listado:
//   <form method="get" data-live="search"> ... <input name="q"> ... </form>
//   <div id="list-region">  ... tabla ... <nav id="list-pagination">...</nav> </div>

(function () {
  const REGION_SEL = "#list-region";
  const PAG_SEL = "#list-pagination";
  const FORM_SEL = "form[data-live='search']";

  function log() { /* console.log.apply(console, arguments); */ }

  function doFetch(url) {
    return fetch(url, {
      method: "GET",
      credentials: "same-origin",
      cache: "no-store",
      headers: { "X-Requested-With": "XMLHttpRequest" }
    }).then(r => {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.text();
    });
  }

  function extractAndSwap(html) {
    const tmp = document.createElement("div");
    tmp.innerHTML = html;
    const nextRegion = tmp.querySelector(REGION_SEL);
    const curRegion = document.querySelector(REGION_SEL);
    if (!nextRegion || !curRegion) {
      // Si no encuentra, degradamos con recarga completa para no dejar muerto el DOM.
      window.location.href = html.match(/<base href="([^"]+)"/) ? window.location.href : window.location.href;
      return;
    }
    curRegion.replaceWith(nextRegion);
    // reatach
    setupLiveSearch(document);
  }

  // Construye URL desde el <form>. Si q está vacío => base sin query (restablece lista)
  function urlFromForm(form) {
    const base = new URL(form.action || window.location.pathname, window.location.origin);
    base.search = "";
    const fd = new FormData(form);
    const q = (fd.get("q") || "").trim();

    if (q === "") {
      // listado inicial, sin q ni page
      return base.toString();
    }
    // copiar todos los parámetros excepto page
    for (const [k, v] of fd.entries()) {
      if (!v) continue;
      if (k === "page") continue;
      base.searchParams.set(k, v);
    }
    // cuando hay q, forzar page=1
    base.searchParams.set("page", "1");
    return base.toString();
  }

  // Debounce helper
  function debounce(fn, wait) {
    let t;
    return function(...args) {
      clearTimeout(t);
      t = setTimeout(() => fn.apply(this, args), wait);
    };
  }

  // --- Core ---
  function setupLiveSearch(root = document) {
    const searchForm = root.querySelector(FORM_SEL);
    if (!searchForm) return;

    // 1) Búsqueda por input (debounced)
    const searchInput = searchForm.querySelector('input[name="q"]');
    if (searchInput && !searchInput._liveBound) {
      let debounceTimer;
      const onInput = function() {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
          searchForm.dispatchEvent(new Event("submit", { cancelable: true }));
        }, 400);
      };
      searchInput.addEventListener('input', onInput);
      searchInput._liveBound = true;
    }

    // 2) Submit del formulario (búsqueda y orden)
    if (!searchForm._liveBoundSubmit) {
      searchForm.addEventListener("submit", function (ev) {
        ev.preventDefault();

        // Construir URL desde form; si q vacío, va a base (restablece)
        const url = urlFromForm(this);

        document.body.style.cursor = "progress";
        doFetch(url).then(html => {
          extractAndSwap(html);
          window.history.replaceState({}, "", url);
        }).catch(e => log("submit error:", e))
          .finally(() => { document.body.style.cursor = ""; });
      });
      searchForm._liveBoundSubmit = true;
    }

    // 2bis) Cambios en selects/inputs del form (orden, filtros adicionales)
    if (!searchForm._liveBoundChange) {
      const onChange = debounce(() => {
        searchForm.dispatchEvent(new Event("submit", { cancelable: true }));
      }, 100);
      searchForm.addEventListener("change", function (e) {
        // cualquier cambio en el form dispara búsqueda
        onChange();
      });
      searchForm._liveBoundChange = true;
    }

    // 3) Paginación por AJAX
    if (!root._liveBoundPagination) {
      root.addEventListener("click", function (ev) {
        const a = ev.target.closest("#list-pagination a.page-link, #list-pagination a");
        if (!a) return;
        ev.preventDefault();
        const href = a.getAttribute("href");
        if (!href) return;

        document.body.style.cursor = "progress";
        doFetch(href).then(html => {
          extractAndSwap(html);
          window.history.replaceState({}, "", href);
        }).catch(e => log("pag error:", e))
          .finally(() => { document.body.style.cursor = ""; });
      });
      root._liveBoundPagination = true;
    }
  }

  // init
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => setupLiveSearch(document));
  } else {
    setupLiveSearch(document);
  }
})();
