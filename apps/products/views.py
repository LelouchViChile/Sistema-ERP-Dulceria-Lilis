from datetime import datetime
import json

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models, transaction
from django.db.models import Q, Sum, CharField, IntegerField, DecimalField, Value
from django.db.models.functions import Cast, Coalesce
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST

from lilis_erp.roles import require_roles

# Excel opcional
try:
    from openpyxl import Workbook
except ImportError:
    Workbook = None

# Modelos
from .models import Producto as Product
from .models import Categoria
from apps.transactional.models import Bodega


# -------------------------- Constantes / helpers --------------------------

ALLOWED_SORT_FIELDS = {"id", "sku", "nombre", "categoria", "stock"}


def _display_categoria(obj):
    cat = getattr(obj, "categoria", None)
    return getattr(cat, "nombre", "") if cat else ""


def _qs_to_dicts(qs):
    """
    Serializa el queryset con las columnas necesarias para la tabla.
    Evita tocar campos no usados en el listado.
    """
    out = []
    for p in qs:
        # stock_total viene anotado; si no, calculamos en caliente (backup)
        st = getattr(p, "stock_total", None)
        if st is None:
            st = p.stocks.aggregate(total=models.Sum("cantidad"))["total"] or 0
        out.append({
            "id": p.id,
            "sku": p.sku or "",
            "nombre": p.nombre or "",
            "categoria": _display_categoria(p),
            "stock": int(st or 0),  # para mostrar entero en la tabla
        })
    return out


def _base_queryset():
    """
    Anota:
    - stock_total: SUM(Stock.cantidad) como DECIMAL (mantiene tipo correcto)
    - id_text: id casteado a texto para búsquedas icontains
    """
    return (
        Product.objects.select_related("categoria")
        .annotate(
            # cantidad es DecimalField(max_digits=14, decimal_places=3)
            stock_total=Coalesce(
                Sum("stocks__cantidad"),
                Value(0),
                output_field=DecimalField(max_digits=14, decimal_places=3),
            ),
            id_text=Cast("id", output_field=CharField()),
        )
    )


def _build_search_q(q: str):
    """
    Búsqueda flexible por SKU, nombre, categoría, y ID (icontains + exacto).
    """
    q = (q or "").strip()
    if not q:
        return Q()

    expr = (
        Q(sku__icontains=q) |
        Q(nombre__icontains=q) |
        Q(categoria__nombre__icontains=q) |
        Q(id_text__icontains=q)
    )
    if q.isdigit():
        expr |= Q(id=int(q))  # ID exacto si es número

    return expr


def _apply_sort(qs, sort_by: str):
    reverse = sort_by.startswith("-")
    key = sort_by.lstrip("-")

    if key not in ALLOWED_SORT_FIELDS:
        key, reverse = "sku", False

    sort_field = {
        "categoria": "categoria__nombre",
        "stock": "stock_total",
    }.get(key, key)

    return qs.order_by(f"-{sort_field}" if reverse else sort_field, "id")


# ---------------- LISTADO ----------------
@login_required
@require_roles("ADMIN", "INVENTARIO", "PRODUCCION", "VENTAS")
def product_list_view(request):
    """
    GET /productos/?q=...&sort=...&page=...
    Renderiza productos.html con tabla, paginación y buscador en vivo.
    """
    query = (request.GET.get("q") or "").strip()
    sort_by = (request.GET.get("sort") or "sku").strip()
    export = (request.GET.get("export") or "").strip()

    # Construcción robusta del queryset
    try:
        qs = _base_queryset()

        if query:
            expr = _build_search_q(query)
            qs = qs.filter(expr)

        qs = _apply_sort(qs, sort_by)

    except Exception as e:
        print("[productos] ERROR building queryset:", e)
        qs = Product.objects.none()

    # Exportación a XLSX
    if export == "xlsx":
        if Workbook is None:
            return HttpResponse("Falta dependencia: pip install openpyxl", status=500)
        wb = Workbook()
        ws = wb.active
        ws.title = "Productos"
        ws.append(["ID", "SKU", "Nombre", "Categoría", "Stock"])
        for p in _qs_to_dicts(qs):
            ws.append([p["id"], p["sku"], p["nombre"], p["categoria"], p["stock"]])
        resp = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        resp["Content-Disposition"] = f'attachment; filename="productos_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
        wb.save(resp)
        return resp

    # Paginación
    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    ctx = {
        "productos": _qs_to_dicts(page_obj.object_list),
        "page_obj": page_obj,
        "query": query,
        "sort_by": sort_by,
        "categorias": Categoria.objects.all(),
        "uom_choices": getattr(Product, "UOMS", []),
        "bodegas": Bodega.objects.all(),
    }
    return render(request, "productos.html", ctx)


# ---------------- BÚSQUEDA (para autocompletar / ajax ligero) ----------------
@login_required
@require_roles("ADMIN", "INVENTARIO", "PRODUCCION", "VENTAS")
def search_products(request):
    """
    GET /productos/search/?q=...
    Devuelve un JSON reducido con hasta 10 coincidencias.
    """
    q = (request.GET.get("q") or "").strip()
    try:
        qs = _base_queryset()

        if q:
            expr = _build_search_q(q)
            qs = qs.filter(expr)

        qs = qs.order_by("id")[:10]
        data = _qs_to_dicts(qs)
    except Exception as e:
        print("[productos.search] ERROR:", e)
        data = []
    return JsonResponse({"results": data})


# ---------------- CRUD ----------------

@login_required
@require_roles("ADMIN", "INVENTARIO", "PRODUCCION", "VENTAS")
@transaction.atomic
def crear_producto(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método no permitido."}, status=405)

    # Acepta JSON o form-data
    if request.headers.get("Content-Type", "").startswith("application/json"):
        data = json.loads(request.body.decode("utf-8") or "{}")
    else:
        data = request.POST

    sku = (data.get("sku") or "").strip().upper()
    nombre = (data.get("nombre") or "").strip()
    categoria_id = (data.get("categoria") or "").strip() or None

    if not sku or not nombre:
        return JsonResponse({"ok": False, "error": "SKU y Nombre son obligatorios."}, status=400)
    if not categoria_id:
        return JsonResponse({"ok": False, "error": "Selecciona una Categoría."}, status=400)
    if Product.objects.filter(sku=sku).exists():
        return JsonResponse({"ok": False, "error": "Ya existe un producto con ese SKU."}, status=400)

    prod = Product.objects.create(
        sku=sku,
        nombre=nombre,
        categoria_id=categoria_id,
        descripcion=data.get("descripcion") or "",
        marca=data.get("marca") or "",
        modelo=data.get("modelo") or "",
    )
    return JsonResponse({"ok": True, "id": prod.id})


@login_required
@require_roles("ADMIN", "INVENTARIO", "PRODUCCION", "VENTAS")
@transaction.atomic
def editar_producto(request, prod_id: int):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método no permitido."}, status=405)

    producto = get_object_or_404(Product, id=prod_id)

    # Acepta JSON o form-data
    if request.headers.get("Content-Type", "").startswith("application/json"):
        data = json.loads(request.body.decode("utf-8") or "{}")
    else:
        data = request.POST

    # Campos editables seguros
    for field in ["sku", "nombre", "descripcion", "marca", "modelo"]:
        if field in data and getattr(producto, field, None) is not None:
            val = (data.get(field) or "").strip()
            setattr(producto, field, val)

    if data.get("categoria"):
        producto.categoria_id = data.get("categoria")

    producto.save()
    return JsonResponse({"ok": True})


@login_required
@require_roles("ADMIN", "INVENTARIO", "PRODUCCION", "VENTAS")
@transaction.atomic
@require_POST
def eliminar_producto(request, prod_id: int):
    producto = get_object_or_404(Product, id=prod_id)
    producto.delete()
    return JsonResponse({"ok": True})
