from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction, models
from datetime import datetime
import json

from lilis_erp.roles import require_roles

try:
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter
except ImportError:
    Workbook = None

from .models import Producto as Product
from .models import Categoria
from apps.transactional.models import Bodega


ALLOWED_SORT_FIELDS = {"id", "sku", "nombre", "categoria", "stock"}


def _display_categoria(obj):
    cat = getattr(obj, "categoria", None)
    return getattr(cat, "nombre", "") if cat else ""


def _qs_to_dicts(qs):
    data = []
    for p in qs:
        total_stock = getattr(p, "stock_total", None)
        if total_stock is None:
            total_stock = p.stocks.aggregate(total=models.Sum("cantidad"))["total"] or 0
        data.append({
            "id": p.id,
            "sku": p.sku or "",
            "nombre": p.nombre or "",
            "categoria": _display_categoria(p),
            "stock": total_stock or 0,
        })
    return data


def _build_search_q(q: str):
    q = (q or "").strip()
    if not q:
        return Q()

    expr = (
        Q(sku__icontains=q) |
        Q(nombre__icontains=q) |
        Q(marca__icontains=q) |
        Q(ean_upc__icontains=q) |
        Q(categoria__nombre__icontains=q)
    )
    if q.isdigit():
        expr |= Q(id=int(q))
    return expr


# ---------------- LISTADO PRINCIPAL ----------------
@login_required
@require_roles("ADMIN", "INVENTARIO", "PRODUCCION", "VENTAS")
def product_list_view(request):
    query = (request.GET.get("q") or "").strip()
    sort_by = (request.GET.get("sort") or "sku").strip()
    export = (request.GET.get("export") or "").strip()

    qs = Product.objects.select_related("categoria").annotate(
        stock_total=Sum("stocks__cantidad")
    )

    if query:
        base_expr = _build_search_q(query)
        if query.isdigit():
            qs = qs.filter(base_expr | Q(stock_total=int(query)))
        else:
            qs = qs.filter(base_expr)

    reverse = sort_by.startswith("-")
    key = sort_by.lstrip("-")
    if key not in ALLOWED_SORT_FIELDS:
        key = "sku"
        reverse = False

    sort_field = {
        "categoria": "categoria__nombre",
        "stock": "stock_total",
    }.get(key, key)

    ordering = f"-{sort_field}" if reverse else sort_field
    qs = qs.order_by(ordering, "id")

    if export == "xlsx":
        if Workbook is None:
            return HttpResponse("Falta dependencia: pip install openpyxl", status=500)

        wb = Workbook()
        ws = wb.active
        ws.title = "Productos"
        headers = ["ID", "SKU", "Nombre", "Categoría", "Stock"]
        ws.append(headers)
        for p in _qs_to_dicts(qs):
            ws.append([p["id"], p["sku"], p["nombre"], p["categoria"], p["stock"]])

        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        filename = f"productos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        wb.save(response)
        return response

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "productos": _qs_to_dicts(page_obj.object_list),
        "page_obj": page_obj,
        "query": query,
        "sort_by": sort_by,
        "categorias": Categoria.objects.all(),
        "uom_choices": Product.UOMS,
        "bodegas": Bodega.objects.all(),
    }
    return render(request, "productos.html", context)


# ---------------- AJAX SEARCH LIVE ----------------
@login_required
@require_roles("ADMIN", "INVENTARIO", "PRODUCCION","VENTAS")
def search_products(request):
    q = (request.GET.get("q") or "").strip()
    qs = Product.objects.annotate(stock_total=Sum("stocks__cantidad"))

    if q:
        expr = _build_search_q(q)
        if q.isdigit():
            qs = qs.filter(expr | Q(stock_total=int(q)))
        else:
            qs = qs.filter(expr)

    qs = qs.order_by("id")[:10]
    return JsonResponse({"results": _qs_to_dicts(qs)})


# ---------------- CRUD ----------------
@login_required
@require_roles("ADMIN", "INVENTARIO", "PRODUCCION","VENTAS")
@transaction.atomic
def crear_producto(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método no permitido."}, status=405)

    data = json.loads(request.body.decode("utf-8")) if request.headers.get("Content-Type","").startswith("application/json") else request.POST

    sku = (data.get("sku") or "").strip().upper()
    nombre = (data.get("nombre") or "").strip()
    categoria_id = (data.get("categoria") or "").strip() or None
    ubicacion_id = (data.get("ubicacion") or "").strip() or None

    if not sku or not nombre:
        return JsonResponse({"ok": False, "error": "SKU y Nombre son obligatorios."}, status=400)
    if not categoria_id:
        return JsonResponse({"ok": False, "error": "Selecciona una Categoría."}, status=400)
    if not ubicacion_id:
        return JsonResponse({"ok": False, "error": "Selecciona una Ubicación."}, status=400)

    if Product.objects.filter(sku=sku).exists():
        return JsonResponse({"ok": False, "error": "El SKU ya existe."}, status=400)

    get_object_or_404(Categoria, id=categoria_id)
    get_object_or_404(Bodega, id=ubicacion_id)

    prod = Product.objects.create(
        sku=sku,
        nombre=nombre,
        categoria_id=categoria_id,
        marca=(data.get("marca") or "").strip(),
        ean_upc=(data.get("codigo_barras") or "").strip(),
        descripcion=(data.get("descripcion") or "").strip(),
    )
    return JsonResponse({"ok": True, "id": prod.id, "message": "Producto creado correctamente."})


@login_required
@csrf_exempt
def eliminar_producto(request, prod_id):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Método no permitido."}, status=405)
    get_object_or_404(Product, id=prod_id).delete()
    return JsonResponse({"status": "ok", "message": "Producto eliminado correctamente."})


@login_required
@require_roles("ADMIN", "INVENTARIO", "PRODUCCION","VENTAS")
@csrf_exempt
def editar_producto(request, prod_id):
    producto = get_object_or_404(Product, id=prod_id)

    if request.method == "GET":
        categorias = list(Categoria.objects.all().values('id', 'nombre'))
        return JsonResponse({
            "id": producto.id,
            "sku": producto.sku,
            "nombre": producto.nombre,
            "categoria": producto.categoria_id or "",
            "categorias": categorias,
            "descripcion": producto.descripcion or "",
            "precio_venta": producto.precio_venta or 0,
            "marca": producto.marca or "",
        })

    if request.method == "POST":
        sku = (request.POST.get("sku") or "").strip()
        nombre = (request.POST.get("nombre") or "").strip()

        if not sku or not nombre:
            return JsonResponse({"status": "error", "message": "SKU y nombre son obligatorios."})
        if Product.objects.filter(sku=sku).exclude(id=producto.id).exists():
            return JsonResponse({"status": "error", "message": "El SKU ya existe."})

        producto.sku = sku
        producto.nombre = nombre
        producto.descripcion = request.POST.get("descripcion") or producto.descripcion
        producto.precio_venta = request.POST.get("precio_venta") or producto.precio_venta
        producto.marca = request.POST.get("marca") or producto.marca

        categoria_id = request.POST.get("categoria")
        if categoria_id:
            producto.categoria_id = categoria_id

        producto.save()
        return JsonResponse({"status": "ok", "message": "Producto actualizado correctamente."})

    return JsonResponse({"status": "error", "message": "Método no permitido."}, status=405)
