from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from lilis_erp.roles import require_roles

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
            "bodega": "Principal", "cantidad": -20, "usuario": "admin",
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
