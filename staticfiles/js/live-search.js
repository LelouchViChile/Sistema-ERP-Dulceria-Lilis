// static/js/live-search.js
// Live search unificado (input debounced + submit + paginación) sin recarga.
// - Teclear en <input name="q"> filtra sin Enter; si queda vacío, vuelve al listado inicial.
// - Cambiar selects/orden también filtra.
// - Paginación por AJAX (sin recargar).
// Requisitos HTML por página de listado:
//   <form method="get" data-live="search"> ... <input name="q"> ... (selects opcionales) ... </form>
//   <tbody id="list-body">, <nav id="list-pagination">, <small id="list-pagination-label">

(function () {
  const FORM_SEL = "form[data-live='search']";

  // --- Utils ---
  function debounce(fn, wait) {
    let t; return (...args)=>{ clearTimeout(t); t=setTimeout(()=>fn.apply(this,args), wait); };
  }

  function fetchText(url) {
    return fetch(url, {
      method: "GET",
      credentials: "same-origin",
      cache: "no-store",
      headers: { "X-Requested-With": "XMLHttpRequest" }
    }).then(r => {
      if (r.redirected && r.url.includes("/login")) {
        window.location.href = r.url; // sesión expirada → login
        throw new Error("Redirect to login");
      }
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.text();
    });
  }

  function swapList(html) {
    const doc = new DOMParser().parseFromString(html, "text/html");
    const newBody  = doc.getElementById("list-body");
    const newPagi  = doc.getElementById("list-pagination");
    const newLabel = doc.getElementById("list-pagination-label");

    if (newBody)  document.getElementById("list-body")?.replaceWith(newBody);
    if (newPagi)  document.getElementById("list-pagination")?.replaceWith(newPagi);
    if (newLabel) document.getElementById("list-pagination-label")?.replaceWith(newLabel);
    // Nota: no reemplazamos el <form>, así los listeners siguen vivos.
  }

  // Construye la URL desde el form. Si q está vacío => listado base (sin query ni page).
  function urlFromForm(form) {
    const base = new URL(form.action || window.location.pathname, window.location.origin);
    base.search = "";
    const fd = new FormData(form);
    const q = (fd.get("q") || "").trim();

    if (!q) return base.toString(); // restablecer

    for (const [k, v] of fd.entries()) {
      if (!v) continue;
      if (k === "page") continue;
      base.searchParams.set(k, v);
    }
    base.searchParams.set("page", "1"); // siempre volver a la página 1 al filtrar
    return base.toString();
  }

  function runSearch(url) {
    document.body.style.cursor = "progress";
    fetchText(url)
      .then(html => {
        swapList(html);
        window.history.replaceState({}, "", url);
      })
      .catch(() => {})
      .finally(() => { document.body.style.cursor = "auto"; });
  }

  // --- Core ---
  function setup(root = document){
    const form = root.querySelector(FORM_SEL);
    if (!form) return;

    // 1) Tecleo en q (debounced)
    const qInput = form.querySelector('input[name="q"]');
    if (qInput && !qInput._liveBound) {
      qInput.addEventListener("input", debounce(() => {
        const url = urlFromForm(form);
        runSearch(url);
      }, 300));
      qInput._liveBound = true;
    }

    // 2) Submit (botón/Enter) reutiliza la misma lógica
    if (!form._liveBoundSubmit) {
      form.addEventListener("submit", (ev) => {
        ev.preventDefault();
        const url = urlFromForm(form);
        runSearch(url);
      });
      form._liveBoundSubmit = true;
    }

    // 3) Cambios en selects (orden/estado/etc)
    if (!form._liveBoundChange) {
      form.addEventListener("change", debounce((e) => {
        if (e.target && (e.target.tagName === "SELECT" || e.target.type === "checkbox" || e.target.type === "radio")) {
          const url = urlFromForm(form);
          runSearch(url);
        }
      }, 150));
      form._liveBoundChange = true;
    }

    // 4) Paginación por AJAX
    if (!root._liveBoundPagination) {
      root.addEventListener("click", (ev) => {
        const a = ev.target.closest("#list-pagination a");
        if (!a) return;
        ev.preventDefault();
        const href = a.getAttribute("href");
        if (!href) return;
        runSearch(href);
      });
      root._liveBoundPagination = true;
    }
  }

  if (document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", () => setup(document));
  } else {
    setup(document);
  }
})();
