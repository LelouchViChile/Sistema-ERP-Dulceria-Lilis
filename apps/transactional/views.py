from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def gestion_transacciones(request):
    """
    Vista principal de gestión de transacciones (movimientos de inventario).
    Por ahora usa datos de ejemplo.
    """
    movimientos_demo = [
        {
            "fecha": "2025-11-01",
            "tipo": "Ingreso",
            "folio": "MOV-001",
            "producto": "Paleta de Caramelo",
            "proveedor": "Dulces San Pedro",
            "bodega": "Principal",
            "cantidad": 100,
            "usuario": "admin",
            "serie": "-",
            "lote": "L001",
            "venc": "2026-01-15",
            "doc_ref": "FC-123"
        },
        {
            "fecha": "2025-11-02",
            "tipo": "Salida",
            "folio": "MOV-002",
            "producto": "Chocolate Almendras",
            "proveedor": "-",
            "bodega": "Principal",
            "cantidad": -20,
            "usuario": "admin",
            "serie": "-",
            "lote": "L002",
            "venc": "2025-12-20",
            "doc_ref": "VT-045"
        },
    ]
    
    context = {"movimientos": movimientos_demo}
    return render(request, "gestion_transacciones.html", context)