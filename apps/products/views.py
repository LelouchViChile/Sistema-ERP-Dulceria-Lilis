from datetime import datetime
import json
import traceback
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction, models
from django.db.models import Q, CharField, DecimalField, Value
from django.db.models.functions import Cast, Coalesce
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST
from django.forms.models import model_to_dict
from django.core.exceptions import FieldError
from django.apps import apps  # <- para cargar Bodega de forma segura

from lilis_erp.roles import require_roles

# Excel opcional
try:
    from openpyxl import Workbook
except ImportError:
    Workbook = None

# Modelos locales
from .models import Producto as Product
from .models import Categoria


# -------------------------- Constantes / helpers --------------------------

ALLOWED_SORT_FIELDS = {
    "id", "-id",
    "sku", "-sku",
    "nombre", "-nombre",
    "categoria", "-categoria",
    "stock", "-stock",
}

# Campo decimal único para todas las anotaciones de stock
DEC = DecimalField(max_digits=14, decimal_places=3)


def _display_categoria(obj):
    cat = getattr(obj, "categoria", None)
    return getattr(cat, "nombre", "") if cat else ""


def _qs_to_dicts(qs):
    out = []
    for p in qs:
        st = getattr(p, "stock_total", Decimal("0"))
        out.append({
            "id": p.id,
            "sku": p.sku or "",
            "nombre": p.nombre or "",
            "categoria": _display_categoria(p),
            "stock": int(st or 0),
        })
    return out


def _base_queryset():
    """
    - id_text para buscar por ID (icontains)
    - stock_total por JOIN + SUM sobre related_name='stocks'
    - Tipado como Decimal para evitar 'mixed types'
    """
    return (
        Product.objects.select_related("categoria")
        .annotate(
            id_text=Cast("id", output_field=CharField()),
            stock_total=Coalesce(
                models.Sum("stocks__cantidad", output_field=DEC),
                Value(Decimal("0"), output_field=DEC),
                output_field=DEC,
            ),
        )
    )


def _build_search_q(q: str):
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
        expr |= Q(id=int(q))
    return expr


def _apply_filters(qs, request):
    """
    Filtros ligeros SIN romper nada de lo tuyo.
    - categoría: ?categoria=<id>  (o ?cat=<id>)
    - estado/activo: ?estado=activos | inactivos   (si el modelo tiene 'activo')
    """
    cat = (request.GET.get("categoria") or request.GET.get("cat") or "").strip()
    if cat.isdigit():
        qs = qs.filter(categoria_id=int(cat))

    estado = (request.GET.get("estado") or "").strip().lower()
    if estado in {"activos", "inactivos"} and hasattr(Product, "activo"):
        qs = qs.filter(activo=(estado == "activos"))

    return qs


def _apply_sort(qs, sort_by: str):
    sort_by = (sort_by or "").strip()
    if sort_by not in ALLOWED_SORT_FIELDS:
        sort_by = "sku"

    reverse = sort_by.startswith("-")
    key = sort_by.lstrip("-")

    sort_field = {
        "categoria": "categoria__nombre",
        "stock": "stock_total",
    }.get(key, key)

    try:
        ordered = qs.order_by(f"-{sort_field}" if reverse else sort_field, "id")
        list(ordered[:1])  # evalúa 1 fila para cazar errores
        return ordered
    except FieldError as e:
        print("[productos] FieldError en order_by:", e)
        traceback.print_exc()
        try:
            ordered = qs.order_by("-sku" if reverse else "sku", "id")
            list(ordered[:1])
            return ordered
        except Exception as e2:
            print("[productos] Fallback a sku también falló, usando id:", e2)
            traceback.print_exc()
            return qs.order_by("-id" if reverse else "id")


def _load_bodegas_safe():
    """Devuelve queryset de Bodega si existe; [] si no existe el modelo."""
    try:
        Bodega = apps.get_model("transactional", "Bodega")
        return Bodega.objects.all() if Bodega is not None else []
    except Exception:
        return []


# ---------------- LISTADO ----------------
@login_required
@require_roles("ADMIN", "INVENTARIO", "PRODUCCION", "VENTAS")
def product_list_view(request):
    """
    GET /productos/?q=...&sort=...&page=...&categoria=...&estado=...
    Renderiza productos.html (compatible con AJAX).
    """
    query = (request.GET.get("q") or "").strip()
    sort_by = (request.GET.get("sort") or "sku").strip()
    export = (request.GET.get("export") or "").strip()

    try:
        qs = _base_queryset()
        if query:
            qs = qs.filter(_build_search_q(query))
        qs = _apply_filters(qs, request)  # <- aplica filtros si vienen
        qs = _apply_sort(qs, sort_by)
    except Exception as e:
        print("[productos] ERROR construyendo queryset:", e)
        traceback.print_exc()
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
        resp = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        resp["Content-Disposition"] = f'attachment; filename="productos_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
        wb.save(resp)
        return resp

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    ctx = {
        "productos": _qs_to_dicts(page_obj.object_list),
        "page_obj": page_obj,
        "query": query,
        "sort_by": sort_by,
        "categorias": Categoria.objects.all(),
        "uom_choices": getattr(Product, "UOMS", []),
        "bodegas": _load_bodegas_safe(),
    }

    # 🔧 Si la solicitud viene por AJAX (live-search), devolvemos solo el fragmento HTML necesario
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return render(request, "partials/_productos_table.html", ctx)

    return render(request, "productos.html", ctx)


# ---------------- BÚSQUEDA (autocompletar / ajax ligero) ----------------
@login_required
@require_roles("ADMIN", "INVENTARIO", "PRODUCCION", "VENTAS")
def search_products(request):
    q = (request.GET.get("q") or "").strip()
    try:
        qs = _base_queryset()
        if q:
            qs = qs.filter(_build_search_q(q))
        qs = _apply_sort(qs, "id")[:10]
        data = _qs_to_dicts(qs)
    except Exception as e:
        print("[productos.search] ERROR:", e)
        traceback.print_exc()
        data = []
    return JsonResponse({"results": data})


# ---------------- CRUD ----------------

@login_required
@require_roles("ADMIN", "INVENTARIO", "PRODUCCION", "VENTAS")
@transaction.atomic
def crear_producto(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método no permitido."}, status=405)

    is_json = (request.headers.get("Content-Type", "") or "").startswith("application/json")
    data = json.loads(request.body.decode("utf-8") or "{}") if is_json else request.POST

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
    producto = get_object_or_404(Product, id=prod_id)

    # GET -> devuelve JSON para cargar modal/form por AJAX
    if request.method == "GET":
        data = model_to_dict(
            producto,
            fields=[
                "id", "sku", "nombre", "descripcion", "marca", "modelo",
                "ean_upc", "stock_minimo", "stock_maximo", "punto_reorden", "categoria"
            ]
        )
        data["categoria_nombre"] = getattr(producto.categoria, "nombre", "")
        data["categorias"] = list(Categoria.objects.values("id", "nombre"))
        return JsonResponse({"ok": True, "data": data})

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método no permitido."}, status=405)

    is_json = (request.headers.get("Content-Type", "") or "").startswith("application/json")
    data = json.loads(request.body.decode("utf-8") or "{}") if is_json else request.POST

    for field in ["sku", "nombre", "descripcion", "marca", "modelo"]:
        if field in data and getattr(producto, field, None) is not None:
            setattr(producto, field, (data.get(field) or "").strip())

    if data.get("categoria"):
        producto.categoria_id = data.get("categoria")

    if "codigo_barras" in data or "ean_upc" in data:
        ean = (data.get("codigo_barras") or data.get("ean_upc") or "").strip()
        producto.ean_upc = ean or None

    for f in ("stock_minimo", "stock_maximo", "punto_reorden"):
        if f in data and hasattr(producto, f):
            try:
                setattr(producto, f, data.get(f))
            except Exception:
                pass

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
