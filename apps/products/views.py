# apps/products/views.py
from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from datetime import datetime

from lilis_erp.roles import require_roles

# Dependencia para exportar Excel
try:
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter
except ImportError:
    Workbook = None  # Se notificará si falta la librería


@login_required
@require_roles("ADMIN", "INVENTARIO", "PRODUCCION", "VENTAS")
def product_list_view(request):
    """
    Vista para mostrar la lista de productos, con búsqueda, paginación y exportación a Excel.
    Por ahora usa datos de ejemplo. Más adelante se integrará con la base de datos.
    """
    # Datos de ejemplo (simulan una consulta)
    productos_ejemplo = [
        {'sku': 'DUL-001', 'nombre': 'Paleta de Caramelo', 'stock': 150},
        {'sku': 'CHO-002', 'nombre': 'Chocolate con Almendras', 'stock': 80},
        {'sku': 'GOM-003', 'nombre': 'Gomitas de Ositos', 'stock': 200},
        {'sku': 'BOM-004', 'nombre': 'Bombón de Menta', 'stock': 120},
        {'sku': 'CAR-005', 'nombre': 'Caramelo de Fresa', 'stock': 300},
    ]

    # --- Filtros de búsqueda, orden y exportación ---
    query = request.GET.get('q', '').strip()
    sort_by = request.GET.get('sort', 'sku')
    export = request.GET.get('export')

    # Filtrar (por nombre o SKU)
    if query:
        productos_ejemplo = [
            p for p in productos_ejemplo
            if query.lower() in p['sku'].lower() or query.lower() in p['nombre'].lower()
        ]

    # Orden simple
    reverse = sort_by.startswith('-')
    key = sort_by.lstrip('-')
    productos_ejemplo.sort(key=lambda x: x.get(key, ''), reverse=reverse)

    # --- Exportación a Excel ---
    if export == 'xlsx':
        if Workbook is None:
            return HttpResponse(
                "Falta dependencia: instala openpyxl (pip install openpyxl)",
                status=500,
                content_type="text/plain; charset=utf-8"
            )

        wb = Workbook()
        ws = wb.active
        ws.title = "Productos"
        headers = ["SKU", "Nombre", "Stock"]
        ws.append(headers)

        for p in productos_ejemplo:
            ws.append([p["sku"], p["nombre"], p["stock"]])

        # Ajustar ancho de columnas
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

    # --- Paginación (10 por página) ---
    paginator = Paginator(productos_ejemplo, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'query': query,
        'sort_by': sort_by,
    }
    return render(request, 'productos.html', context)
