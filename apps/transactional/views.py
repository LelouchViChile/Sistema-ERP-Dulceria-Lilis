from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from lilis_erp.roles import require_roles
from django.views.decorators.http import require_POST
import openpyxl
from django.http import HttpResponse

from .models import MovimientoInventario  # usa el modelo real
# Si aun no tienes datos en BD, la vista HTML sigue mostrando el demo
# pero el endpoint /transactional/search/ ya consultará la BD real.


@login_required
@require_roles("ADMIN", "PRODUCCION")
def gestion_transacciones(request):
    """
    Vista principal de gestión de transacciones (movimientos de inventario).
    Mantiene la grilla DEMO visual, pero el buscador Ajax sí consulta la BD real.
    """
    movimientos_demo = [
        {
            "folio": 1001, "fecha": "2025-11-05", "tipo": "Ingreso",
            "producto": "Cacao 70% 1kg", "proveedor": "CacaoPro",
            "bodega": "Principal", "cantidad": 50, "usuario": "admin",
            "serie": "-", "lote": "L001", "venc": "2026-01-15", "doc_ref": "OC-009"
        },
        {
            "folio": 1002, "fecha": "2025-11-05", "tipo": "Salida",
            "producto": "Chocolate Almendras", "proveedor": "-",
            "bodega": "Principal", "cantidad": 20, "usuario": "admin",
            "serie": "-", "lote": "L002", "venc": "2025-12-20", "doc_ref": "VT-045"
        },
        {
            "folio": 1003, "fecha": "2025-11-04", "tipo": "Transferencia",
            "producto": "Azúcar 25kg", "proveedor": "-",
            "bodega": "Secundaria → Principal", "cantidad": 25, "usuario": "jefe",
            "serie": "-", "lote": "-", "venc": "-", "doc_ref": "TR-010"
        },
    ]
    context = {"movimientos": movimientos_demo}
    return render(request, "gestion_transacciones.html", context)


@login_required
@require_roles("ADMIN", "PRODUCCION", "INVENTARIO", "VENTAS")
def search_transactions(request):
    """
    Endpoint AJAX (JSON): retorna máx. 10 movimientos filtrados por 'q'.
    Busca por: producto.nombre, producto.sku, tipo, proveedor.razon_social
    """
    q = (request.GET.get("q") or "").strip()
    if not q:
        return JsonResponse({"results": []})

    qs = (
        MovimientoInventario.objects
        .select_related("producto", "proveedor")
        .filter(
            Q(producto__nombre__icontains=q) |
            Q(producto__sku__icontains=q) |
            Q(tipo__icontains=q) |
            Q(proveedor__razon_social__icontains=q)
        )
        .order_by("-fecha")[:10]
    )

    data = []
    for m in qs:
        data.append({
            "id": m.id,
            "fecha": (m.fecha.date().isoformat() if hasattr(m.fecha, "date") else m.fecha),
            "tipo": dict(MovimientoInventario.TIPOS).get(m.tipo, m.tipo),
            "producto": f"{getattr(m.producto, 'sku', '')} - {getattr(m.producto, 'nombre', '')}",
            "proveedor": getattr(m.proveedor, "razon_social", "") or "—",
            "cantidad": float(m.cantidad),
            "uom": getattr(m.producto, "uom_venta", "") or "",
        })
    return JsonResponse({"results": data})

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