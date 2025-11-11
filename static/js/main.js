// main.js — Búsqueda AJAX robusta con delegación y re-wire automático
(function () {
  function log(){ try{ console.log.apply(console, arguments); }catch(_){} }

  function debounce(fn, wait){
    let t; return (...a)=>{ clearTimeout(t); t=setTimeout(()=>fn.apply(null,a), wait); };
  }

  function serializeForm(form){
    const fd = new FormData(form);
    const p = new URLSearchParams();
    for (const [k,v] of fd.entries()){
      if (v !== '' && v != null) p.append(k, v); // evita keys vacías
    }
    return p.toString();
  }

  function extractAndSwap(htmlText){
    // DOM temporal para encontrar #list-body y #list-pagination
    const dom = document.createElement("html");
    dom.innerHTML = htmlText;

    const newBody = dom.querySelector("#list-body");
    const newPag  = dom.querySelector("#list-pagination");

    const curBody = document.querySelector("#list-body");
    const curPag  = document.querySelector("#list-pagination");

    if (newBody && curBody) curBody.innerHTML = newBody.innerHTML;
    if (newPag  && curPag ) curPag.innerHTML  = newPag.innerHTML;

    // tras reemplazar, asegurar wiring (paginación)
    wirePagination();
  }

  async function doFetch(url, opts = {}){
    const res = await fetch(url, {
      method: "GET",
      credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest" },
      ...opts
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.text();
  }

  async function refreshFromForm(form){
    const url = form.action || window.location.pathname;
    const qs  = serializeForm(form);
    const full = qs ? `${url}?${qs}` : url;

    try{
      document.body.style.cursor = "progress";
      const html = await doFetch(full);
      extractAndSwap(html);
      window.history.replaceState({}, "", full); // actualiza URL sin recargar
    }catch(e){
      log("[live-search] error:", e);
    }finally{
      document.body.style.cursor = "";
    }
  }

  // —— wiring principal —— //
  function setupLiveSearch(root = document){
    const form = root.querySelector('form[data-live="search"]');
    if (!form) return;

    // evita doble wiring
    if (form.__liveReady) return;
    form.__liveReady = true;

    // 1) Submit (Enter o botón) — siempre AJAX
    form.addEventListener("submit", ev => {
      ev.preventDefault();
      refreshFromForm(form);
    });

    // 2) Delegación de 'input' (sobrevive a cambios)
    const debounced = debounce(() => refreshFromForm(form), 300);
    form.addEventListener("input", ev => {
      const el = ev.target;
      if (!el) return;
      // dispara en text, search, number, email, etc.
      if (el.matches('input, textarea')) debounced();
    });

    // 3) Cambios en select/checkbox/radio
    form.addEventListener("change", ev => {
      const el = ev.target;
      if (!el) return;
      if (el.matches('select, input[type="checkbox"], input[type="radio"]')) {
        refreshFromForm(form);
      }
    });

    // 4) Paginación por delegación
    wirePagination();
  }

  function wirePagination(){
    const pag = document.querySelector("#list-pagination");
    if (!pag || pag.__wired) return;
    pag.__wired = true;

    pag.addEventListener("click", ev => {
      const a = ev.target.closest("a[href]");
      if (!a) return;
      ev.preventDefault();
      doFetch(a.href)
        .then(html => {
          extractAndSwap(html);
          window.history.replaceState({}, "", a.href);
        })
        .catch(err => log(err));
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    setupLiveSearch(document);
    log("[live-search] listo");
  });
})();
