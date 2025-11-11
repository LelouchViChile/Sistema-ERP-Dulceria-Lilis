// static/js/live-search.js
// Live search unificado (input debounced + submit + paginación) sin recarga.
// - Escribir/borrar en <input name="q">: filtra y si está vacío vuelve al listado inicial.
// - Submit del form (orden/otros filtros): AJAX.
// - Paginación: AJAX.
// Requiere en el HTML:
//   <form method="get" data-live="search"> ... <input name="q"> ... </form>
//   <tbody id="list-body">, <nav id="list-pagination">, <small id="list-pagination-label">

(function () {
  const FORM_SEL = "form[data-live='search']";

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

  function swapList(html) {
    const doc = new DOMParser().parseFromString(html, "text/html");
    const newBody  = doc.getElementById("list-body");
    const newPagi  = doc.getElementById("list-pagination");
    const newLabel = doc.getElementById("list-pagination-label");
    if (newBody)  document.getElementById("list-body")?.replaceWith(newBody);
    if (newPagi)  document.getElementById("list-pagination")?.replaceWith(newPagi);
    if (newLabel) document.getElementById("list-pagination-label")?.replaceWith(newLabel);
  }

  function debounce(fn, wait) {
    let t; return (...args)=>{ clearTimeout(t); t=setTimeout(()=>fn.apply(this,args), wait); };
  }

  function urlFromForm(form) {
    const base = new URL(form.action || window.location.pathname, window.location.origin);
    base.search = "";
    const fd = new FormData(form);
    const q = (fd.get("q") || "").trim();

    if (!q) {
      // listado inicial sin filtros
      return base.toString();
    }
    for (const [k,v] of fd.entries()) {
      if (!v) continue;
      if (k === "page") continue;
      base.searchParams.set(k, v);
    }
    base.searchParams.set("page", "1"); // al escribir, volvemos a pag 1
    return base.toString();
  }

  function setup(root=document){
    const form = root.querySelector(FORM_SEL);
    if (!form) return;

    const qInput = form.querySelector('input[name="q"]');
    if (qInput && !qInput._liveBound) {
      qInput.addEventListener("input", debounce(() => {
        form.dispatchEvent(new Event("submit", { cancelable: true }));
      }, 300));
      qInput._liveBound = true;
    }

    if (!form._liveBoundSubmit){
      form.addEventListener("submit", (ev) => {
        ev.preventDefault();
        const url = urlFromForm(form);
        document.body.style.cursor = "progress";
        doFetch(url).then(html=>{
          swapList(html);
          window.history.replaceState({}, "", url);
        }).finally(()=>{ document.body.style.cursor = "auto"; });
      });
      form._liveBoundSubmit = true;
    }

    if (!root._liveBoundPagination){
      root.addEventListener("click", (ev)=>{
        const a = ev.target.closest("#list-pagination a");
        if (!a) return;
        ev.preventDefault();
        const href = a.getAttribute("href");
        if (!href) return;
        document.body.style.cursor = "progress";
        doFetch(href).then(html=>{
          swapList(html);
          window.history.replaceState({}, "", href);
        }).finally(()=>{ document.body.style.cursor = "auto"; });
      });
      root._liveBoundPagination = true;
    }
  }

  if (document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", ()=>setup(document));
  } else {
    setup(document);
  }
})();
