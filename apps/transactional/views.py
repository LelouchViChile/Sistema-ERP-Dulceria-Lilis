from datetime import datetime
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.core.paginator import Paginator
from lilis_erp.roles import require_roles
from django.views.decorators.http import require_POST
import json

from .models import MovimientoInventario, Producto, Proveedor

try:
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter
except ImportError:
    Workbook = None


def _build_transaction_q(q: str):
    """Construye un Q de búsqueda para movimientos de inventario."""
    q = (q or "").strip()
    if not q:
        return Q()
    return (
        Q(producto__nombre__icontains=q) |
        Q(producto__sku__icontains=q) |
        Q(tipo__icontains=q) |
        Q(proveedor__razon_social__icontains=q) |
        Q(lote__icontains=q) |
        Q(serie__icontains=q) |
        Q(creado_por__username__icontains=q)
    )


@login_required
@require_roles("ADMIN", "PRODUCCION", "INVENTARIO", "VENTAS", "COMPRAS")
def gestion_transacciones(request):
    """
    Vista para listar, filtrar, ordenar y exportar movimientos de inventario.
    """
    query = request.GET.get('q', '')
    sort_by = request.GET.get('sort', '-fecha')
    export = request.GET.get('export', '')

    valid_sort_fields = ['fecha', '-fecha', 'producto__nombre', '-producto__nombre', 'tipo', '-tipo']
    if sort_by not in valid_sort_fields:
        sort_by = '-fecha'

    qs = MovimientoInventario.objects.select_related(
        'producto', 'proveedor', 'bodega_origen', 'bodega_destino', 'creado_por'
    ).all()

    if query:
        qs = qs.filter(_build_transaction_q(query))

    qs = qs.order_by(sort_by)

    if export == "xlsx":
        if Workbook is None:
            return HttpResponse("Falta dependencia: instala openpyxl (pip install openpyxl)", status=500)

        wb = Workbook()
        ws = wb.active
        ws.title = "Movimientos"
        headers = [
            "ID", "Fecha", "Tipo", "Producto", "SKU", "Cantidad", "Bodega Origen", "Bodega Destino",
            "Proveedor", "Lote", "Serie", "Vencimiento", "Usuario", "Observación"
        ]
        ws.append(headers)

        for m in qs:
            ws.append([
                m.id,
                m.fecha.strftime('%Y-%m-%d %H:%M'),
                m.get_tipo_display(),
                m.producto.nombre,
                m.producto.sku,
                m.cantidad,
                m.bodega_origen.nombre if m.bodega_origen else "-",
                m.bodega_destino.nombre if m.bodega_destino else "-",
                m.proveedor.razon_social if m.proveedor else "-",
                m.lote or "-",
                m.serie or "-",
                m.fecha_vencimiento.strftime('%Y-%m-%d') if m.fecha_vencimiento else "-",
                m.creado_por.username if m.creado_por else "Sistema",
                m.observacion
            ])

        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                max_len = max(max_len, len(str(cell.value)) if cell.value else 0)
            ws.column_dimensions[col_letter].width = min(max_len + 2, 50)

        response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        filename = f"movimientos_inventario_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        wb.save(response)
        return response

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "movimientos": page_obj.object_list,
        "page_obj": page_obj,
        "query": query,
        "sort_by": sort_by,
    }
    return render(request, "gestion_transacciones.html", context)


@login_required
@require_roles("ADMIN", "PRODUCCION", "INVENTARIO")
@require_POST
def crear_transaccion(request):
    """
    Crea una nueva transacción.
    """
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Payload inválido"}, status=400)

    # Validaciones básicas
    errors = {}
    tipo = (data.get("tipo") or "").strip()
    fecha = (data.get("fecha") or "").strip()
    cantidad = data.get("cantidad")
    producto_id = data.get("producto_id")
    proveedor_id = data.get("proveedor_id")

    if not tipo:
        errors["tipo"] = "Tipo requerido."
    if not fecha:
        errors["fecha"] = "Fecha requerida."
    try:
        cantidad = float(cantidad)
        if cantidad < 0:
            errors["cantidad"] = "Cantidad no puede ser negativa."
    except Exception:
        errors["cantidad"] = "Cantidad inválida."

    if errors:
        return JsonResponse({"ok": False, "errors": errors}, status=400)

    try:
        producto = Producto.objects.get(id=producto_id)
    except Producto.DoesNotExist:
        return JsonResponse({"ok": False, "errors": {"producto": "Producto no encontrado"}}, status=404)

    proveedor = None
    if proveedor_id:
        try:
            proveedor = Proveedor.objects.get(id=proveedor_id)
        except Proveedor.DoesNotExist:
            proveedor = None

    mov = MovimientoInventario.objects.create(
        fecha=fecha,
        tipo=tipo,
        producto=producto,
        proveedor=proveedor,
        cantidad=cantidad,
        usuario=request.user
    )
    return JsonResponse({"ok": True, "id": mov.id})


@login_required
@require_roles("ADMIN", "PRODUCCION", "INVENTARIO")
def editar_transaccion(request, mov_id):
    try:
        mov = MovimientoInventario.objects.get(id=mov_id)
    except MovimientoInventario.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Movimiento no encontrado"}, status=404)

    if request.method == "GET":
        return JsonResponse({
            "ok": True,
            "movimiento": {
                "id": mov.id,
                "fecha": mov.fecha.isoformat() if mov.fecha else "",
                "tipo": mov.tipo,
                "producto": getattr(mov.producto, "id", None),
                "proveedor": getattr(mov.proveedor, "id", None),
                "cantidad": mov.cantidad,
            }
        })

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Payload inválido"}, status=400)

    mov.tipo = data.get("tipo", mov.tipo)
    mov.cantidad = data.get("cantidad", mov.cantidad)
    mov.save()

    return JsonResponse({"ok": True})


@login_required
@require_roles("ADMIN", "PRODUCCION", "INVENTARIO")
def eliminar_transaccion(request, mov_id):
    try:
        MovimientoInventario.objects.get(id=mov_id).delete()
        return JsonResponse({"ok": True})
    except MovimientoInventario.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Movimiento no encontrado"}, status=404)
    
@login_required
@require_roles("ADMIN", "PRODUCCION", "INVENTARIO", "VENTAS")
def export_xlsx(request):
    """
    Exporta los movimientos de inventario a un archivo Excel.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Movimientos"

    headers = [
        "Fecha", "Tipo", "Producto", "Proveedor", "Cantidad",
        "Usuario", "Lote", "Serie", "Vencimiento", "Doc Ref"
    ]
    ws.append(headers)

    movimientos = MovimientoInventario.objects.select_related("producto", "proveedor").order_by("-fecha")

    for m in movimientos:
        ws.append([
            m.fecha.strftime("%Y-%m-%d"),
            dict(MovimientoInventario.TIPOS).get(m.tipo, m.tipo),
            getattr(m.producto, "nombre", ""),
            getattr(m.proveedor, "razon_social", ""),
            m.cantidad,
            m.usuario.username,
            m.lote or "",
            m.serie or "",
            m.vencimiento.strftime("%Y-%m-%d") if m.vencimiento else "",
            m.doc_ref or ""
        ])

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="movimientos.xlsx"'
    wb.save(response)
    return response