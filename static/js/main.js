document.addEventListener("DOMContentLoaded", () => {
  // ===============================
  // main.js — Búsqueda AJAX en vivo
  // ===============================
  // Funciona con <form method="get" data-live="search">
  // Reemplaza <tbody id="list-body">, <nav id="list-pagination"> y <small id="list-pagination-label">
  // Vuelve al listado completo (página 1) cuando el campo 'q' queda vacío.
  // ===============================
  console.log("[live-search] Inicializando...");

  // --- Helpers ---
  function debounce(fn, delay = 300) {
    let timer;
    return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn.apply(this, args), delay); };
  }

  function extractAndSwap(htmlText) {
    const dom = document.createElement("html");
    dom.innerHTML = htmlText;

    const newBody = dom.querySelector("#list-body");
    const newPagi = dom.querySelector("#list-pagination");
    const newLabel = dom.querySelector("#list-pagination-label");

    if (newBody) document.getElementById("list-body")?.replaceWith(newBody);
    if (newPagi) document.getElementById("list-pagination")?.replaceWith(newPagi);
    if (newLabel) document.getElementById("list-pagination-label")?.replaceWith(newLabel);
  }

  async function doFetch(url) {
    const res = await fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } });
    const text = await res.text();
    // Si la sesión expira, el servidor redirige al login.
    if (res.redirected && res.url.includes("/login")) {
      window.location.href = res.url;
    }
    return { ok: res.ok, status: res.status, text, finalUrl: res.url };
  }

  function setupLiveSearch(root = document) {
    const form = root.querySelector('form[data-live="search"]');
    if (!form) {
      console.warn("[live-search] No se encontró form[data-live='search']");
      return;
    }

    const performSearch = async (url) => {
      document.body.style.cursor = "progress";
      try {
        const { ok, text } = await doFetch(url);
        if (ok) {
          extractAndSwap(text);
          window.history.replaceState({}, "", url);
        } else {
          console.error("[live-search] La respuesta del servidor no fue OK.");
        }
      } catch (err) {
        console.error("[live-search] Error en fetch:", err);
      } finally {
        document.body.style.cursor = "auto";
      }
    };

    // --- Lógica de eventos ---

    // 1. Búsqueda al escribir (con debounce)
    const onInput = debounce(() => {
      const url = new URL(form.action || window.location.href);
      const fd = new FormData(form);
      fd.forEach((val, key) => url.searchParams.set(key, val));
      // Al escribir, siempre se va a la página 1.
      url.searchParams.delete("page");
      performSearch(url.toString());
    }, 350);

    form.querySelector("input[name='q']")?.addEventListener("input", onInput);

    // 2. Búsqueda al cambiar un filtro (select)
    form.addEventListener("change", (ev) => {
      if (ev.target.tagName === "SELECT") {
        form.dispatchEvent(new Event("submit", { cancelable: true }));
      }
    });

    // 3. Búsqueda al presionar Enter o el botón de buscar
    form.addEventListener("submit", (ev) => {
      ev.preventDefault();
      onInput(); // Reutilizamos la misma lógica
    });

    // 4. Paginación por AJAX
    root.addEventListener("click", (ev) => {
      const link = ev.target.closest("#list-pagination a");
      if (link) {
        ev.preventDefault();
        const href = link.getAttribute("href");
        if (href) {
          performSearch(href);
        }
      }
    });
  }

  setupLiveSearch(document);
  console.log("[live-search] Listo.");
});
 