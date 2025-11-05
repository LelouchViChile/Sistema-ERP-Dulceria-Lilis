from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from datetime import datetime

from lilis_erp.roles import require_roles

# ===== Excel (opcional) =====
try:
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter
except ImportError:
    Workbook = None  # se notificará si falta la librería

# ===== Modelo correcto =====
# Tu modelo se llama "Producto", lo importamos y lo aliasamos como Product para mantener el resto del código limpio.
from .models import Producto as Product


# -------- Helpers --------
ALLOWED_SORT_FIELDS = {"id", "sku", "nombre", "categoria", "stock"}


def _display_categoria(obj):
    """
    Devuelve un string para la categoría sin forzar el acceso a la FK
    si está vacía o si la FK quedó apuntando a un ID inexistente.
    """
    cat_id = getattr(obj, "categoria_id", None)
    if not cat_id:
        return ""

    try:
        cat = getattr(obj, "categoria", None)
        if cat is None:
            return ""
        return getattr(cat, "nombre", str(cat)) or ""
    except Exception:
        return ""


def _qs_to_dicts(qs):
    """
    Convierte un queryset de Product a lista de dicts con los campos usados en la tabla/buscador.
    """
    data = []
    for p in qs:
        data.append({
            "id": p.id,
            "sku": getattr(p, "sku", ""),
            "nombre": getattr(p, "nombre", getattr(p, "name", "")),
            "categoria": _display_categoria(p),
            "stock": getattr(p, "stock", 0),
        })
    return data


def _build_search_q(q: str):
    """
    Construye un Q de búsqueda compatible con los campos existentes del modelo.
    Soporta FK a 'categoria' correctamente (usa nombre de la categoría).
    """
    q = (q or "").strip()
    if not q:
        return Q()

    names = {f.name for f in Product._meta.get_fields()}
    expr = Q()

    if "sku" in names:
        expr |= Q(sku__icontains=q)
    if "nombre" in names:
        expr |= Q(nombre__icontains=q)
    if "name" in names:
        expr |= Q(name__icontains=q)

    # si existe FK a categoria
    if "categoria" in names:
        try:
            expr |= Q(categoria__nombre__icontains=q)
        except Exception:
            expr |= Q(categoria__icontains=q)

    if "category" in names:
        try:
            expr |= Q(category__nombre__icontains=q)
        except Exception:
            expr |= Q(category__icontains=q)

    return expr


# ===================== VISTAS =====================

@login_required
@require_roles("ADMIN", "INVENTARIO", "PRODUCCION", "VENTAS")
def product_list_view(request):
    """
    Listado HTML con:
    - Filtro por q (sku, nombre, categoria*)
    - Orden por sort (id, sku, nombre, categoria, stock)
    - Paginación (10)
    - Exportar Excel (?export=xlsx)
    """
    query = (request.GET.get("q") or "").strip()
    sort_by = (request.GET.get("sort") or "sku").strip()
    export = (request.GET.get("export") or "").strip()

    qs = Product.objects.all()

    if query:
        qs = qs.filter(_build_search_q(query))

    reverse = sort_by.startswith("-")
    key = sort_by.lstrip("-")
    if key not in ALLOWED_SORT_FIELDS:
        key = "sku"
        reverse = False
    ordering = f"-{key}" if reverse else key
    qs = qs.order_by(ordering)

    # Exportar a Excel
    if export == "xlsx":
        if Workbook is None:
            return HttpResponse(
                "Falta dependencia: instala openpyxl (pip install openpyxl)",
                status=500,
                content_type="text/plain; charset=utf-8",
            )

        wb = Workbook()
        ws = wb.active
        ws.title = "Productos"
        headers = ["ID", "SKU", "Nombre", "Categoría", "Stock"]
        ws.append(headers)

        for p in qs:
            ws.append([
                p.id,
                getattr(p, "sku", ""),
                getattr(p, "nombre", getattr(p, "name", "")),
                _display_categoria(p),
                getattr(p, "stock", 0),
            ])

        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                max_len = max(max_len, len(str(cell.value)) if cell.value else 0)
            ws.column_dimensions[col_letter].width = min(max_len + 2, 50)

        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        filename = f"productos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        wb.save(response)
        return response

    paginator = Paginator(qs, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "productos": _qs_to_dicts(page_obj.object_list),
        "page_obj": page_obj,
        "query": query,
        "sort_by": sort_by,
    }
    return render(request, "productos.html", context)


@login_required
@require_roles("ADMIN", "INVENTARIO", "PRODUCCION", "VENTAS")
def search_products(request):
    """
    Endpoint AJAX (JSON): retorna máx. 10 productos filtrados por 'q'.
    """
    q = (request.GET.get("q") or "").strip()
    qs = Product.objects.all()
    if q:
        qs = qs.filter(_build_search_q(q))

    qs = qs.order_by("id")[:10]
    return JsonResponse({"results": _qs_to_dicts(qs)})
