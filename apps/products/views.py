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

# Excel (opcional)
try:
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter
except ImportError:
    Workbook = None

# Modelo correcto
from .models import Producto as Product
from .models import Categoria
from apps.transactional.models import Bodega

# ---------------- Config ----------------
ALLOWED_SORT_FIELDS = {"id", "sku", "nombre", "categoria", "stock"}

# ---------------- Helpers ----------------
def _display_categoria(obj):
    cat_id = getattr(obj, "categoria_id", None)
    if not cat_id:
        return ""
    cat = getattr(obj, "categoria", None)
    if not cat:
        return ""
    return getattr(cat, "nombre", str(cat)) or ""

def _qs_to_dicts(qs):
    data = []
    for p in qs:
        total_stock = getattr(p, "stock_total", None)
        if total_stock is None:
            total_stock = p.stocks.aggregate(total=models.Sum("cantidad"))["total"] or 0
        data.append({
            "id": p.id,
            "sku": getattr(p, "sku", ""),
            "nombre": getattr(p, "nombre", getattr(p, "name", "")),
            "categoria": _display_categoria(p),
            "stock": total_stock or 0,
        })
    return data

def _build_search_q(q: str):
    """
    Busca por:
      - sku, nombre, marca, ean_upc, categoria__nombre (icontains)
      - id (si q es número)
      *Nota*: NO usamos 'stock_total' aquí para evitar errores; lo manejamos fuera.
    """
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
    try:
        expr |= Q(id=int(q))
    except (ValueError, TypeError):
        pass
    return expr

# ---------------- Vistas ----------------
@login_required
@require_roles("ADMIN", "INVENTARIO", "PRODUCCION", "VENTAS")
def product_list_view(request):
    """
    Listado HTML con:
    - Filtro por q (sku, nombre, marca, ean_upc, categoría, id; además stock exacto si q es número)
    - Orden por sort (id, sku, nombre, categoria, stock)
    - Paginación
    - Export a Excel (?export=xlsx)
    """
    query = (request.GET.get("q") or "").strip()
    sort_by = (request.GET.get("sort") or "sku").strip()
    export = (request.GET.get("export") or "").strip()

    # Siempre anotamos stock_total una sola vez
    qs = Product.objects.select_related("categoria").annotate(
        stock_total=Sum("stocks__cantidad")
    )

    # Filtro principal
    if query:
        base_expr = _build_search_q(query)
        # Si q es numérico, además permitir match exacto por stock_total
        try:
            num = int(query)
            qs = qs.filter(base_expr | Q(stock_total=num))
        except (ValueError, TypeError):
            qs = qs.filter(base_expr)

    # Orden
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
    qs = qs.order_by(ordering, "id")  # desempatamos por id para estabilidad

    # Export
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
        for p in _qs_to_dicts(qs):
            ws.append([p["id"], p["sku"], p["nombre"], p["categoria"], p["stock"]])

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

    # Paginación
    paginator = Paginator(qs, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

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

@login_required
@require_roles("ADMIN", "INVENTARIO", "PRODUCCION","VENTAS")
def search_products(request):
    q = (request.GET.get("q") or "").strip()
    qs = Product.objects.annotate(stock_total=Sum("stocks__cantidad"))
    if q:
        try:
            num = int(q)
            qs = qs.filter(_build_search_q(q) | Q(stock_total=num))
        except (ValueError, TypeError):
            qs = qs.filter(_build_search_q(q))
    qs = qs.order_by("id")[:10]
    return JsonResponse({"results": _qs_to_dicts(qs)})

@login_required
@require_roles("ADMIN", "INVENTARIO", "PRODUCCION","VENTAS")
@transaction.atomic
def crear_producto(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método no permitido."}, status=405)

    is_json = request.headers.get("Content-Type", "").startswith("application/json")
    if is_json:
        try:
            data = json.loads(request.body.decode("utf-8"))
        except Exception:
            return JsonResponse({"ok": False, "error": "JSON inválido."}, status=400)
    else:
        data = request.POST

    sku           = (data.get("sku") or "").strip().upper()
    nombre        = (data.get("nombre") or "").strip()
    categoria_id  = (data.get("categoria") or "").strip() or None
    descripcion   = (data.get("descripcion") or "").strip()
    precio_compra = (data.get("precio_compra") or "").strip()
    precio_venta  = (data.get("precio_venta") or "").strip()
    marca         = (data.get("marca") or "").strip()
    ean_upc       = (data.get("codigo_barras") or "").strip()
    ubicacion_id  = (data.get("ubicacion") or "").strip()
    uom           = (data.get("uom") or "UN").strip()
    stock_min     = (data.get("stock_min") or "").strip()
    stock_max     = (data.get("stock_max") or "").strip()
    estado        = (data.get("estado") or "Activo").strip()

    if not sku or not nombre:
        return JsonResponse({"ok": False, "error": "SKU y Nombre son obligatorios."}, status=400)
    if not categoria_id:
        return JsonResponse({"ok": False, "error": "Selecciona una Categoría."}, status=400)
    if not ubicacion_id:
        return JsonResponse({"ok": False, "error": "Selecciona una Ubicación."}, status=400)

    def to_decimal(val, default=None):
        if val in (None, ""): return default
        try: return float(val)
        except Exception: return None

    costo_estandar = to_decimal(precio_compra, default=None)
    precio_venta_f = to_decimal(precio_venta, default=None)
    stock_minimo   = to_decimal(stock_min,   default=0)
    stock_maximo   = to_decimal(stock_max,   default=None)

    if precio_venta and precio_venta_f is None:
        return JsonResponse({"ok": False, "error": "Precio de venta inválido."}, status=400)
    if precio_compra and costo_estandar is None:
        return JsonResponse({"ok": False, "error": "Precio de compra inválido."}, status=400)
    if stock_min and stock_minimo is None:
        return JsonResponse({"ok": False, "error": "Stock mínimo inválido."}, status=400)
    if stock_max and stock_maximo is None:
        return JsonResponse({"ok": False, "error": "Stock máximo inválido."}, status=400)

    get_object_or_404(Categoria, id=categoria_id)
    get_object_or_404(Bodega, id=ubicacion_id)

    if Product.objects.filter(sku=sku).exists():
        return JsonResponse({"ok": False, "error": "El SKU ya existe."}, status=400)

    activo = (estado.upper() == "ACTIVO")

    try:
        prod = Product.objects.create(
            sku=sku,
            ean_upc=ean_upc or None,
            nombre=nombre,
            descripcion=descripcion,
            categoria_id=categoria_id,
            marca=marca or "",
            uom_compra=uom,
            uom_venta=uom,
            factor_conversion=1,
            costo_estandar=costo_estandar if costo_estandar is not None else None,
            precio_venta=precio_venta_f if precio_venta_f is not None else None,
            impuesto_iva=19,
            stock_minimo=stock_minimo if stock_minimo is not None else 0,
            stock_maximo=stock_maximo,
            punto_reorden=None,
            perecible=False,
            control_por_lote=False,
            control_por_serie=False,
            url_imagen="",
            url_ficha_tecnica="",
            activo=activo,
        )
        return JsonResponse({"ok": True, "id": prod.id, "message": "Producto creado correctamente."})
    except Exception as e:
        return JsonResponse({"ok": False, "error": f"No se pudo crear: {e}"}, status=500)

@login_required
@csrf_exempt
def eliminar_producto(request, prod_id):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Método no permitido."}, status=405)
    producto = get_object_or_404(Product, id=prod_id)
    producto.delete()
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
        categoria_id = request.POST.get("categoria") or None
        descripcion = (request.POST.get("descripcion") or "").strip()
        precio_venta = request.POST.get("precio_venta") or 0
        marca = (request.POST.get("marca") or "").strip()

        if not sku or not nombre:
            return JsonResponse({"status": "error", "message": "SKU y nombre son obligatorios."})
        if Product.objects.filter(sku=sku).exclude(id=producto.id).exists():
            return JsonResponse({"status": "error", "message": "El SKU ya existe."})

        producto.sku = sku
        producto.nombre = nombre
        if categoria_id:
            producto.categoria_id = categoria_id
        producto.descripcion = descripcion or producto.descripcion
        producto.precio_venta = precio_venta or producto.precio_venta
        producto.marca = marca or producto.marca

        update_fields = ["sku", "nombre", "descripcion", "precio_venta", "marca"]
        if categoria_id:
            update_fields.append("categoria_id")
        producto.save(update_fields=update_fields)

        return JsonResponse({"status": "ok", "message": "Producto actualizado correctamente."})

    return JsonResponse({"status": "error", "message": "Método no permitido."}, status=405)
