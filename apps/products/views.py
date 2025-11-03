from django.shortcuts import render
from django.contrib.auth.decorators import login_required

# Create your views here.

@login_required
def product_list_view(request):
    """
    Vista para mostrar la lista de productos y el formulario de gestión.
    """
    # Por ahora, usaremos datos de ejemplo para la tabla.
    # Más adelante, estos datos vendrán de la base de datos.
    productos_ejemplo = [
        {'sku': 'DUL-001', 'nombre': 'Paleta de Caramelo', 'stock': 150},
        {'sku': 'CHO-002', 'nombre': 'Chocolate con Almendras', 'stock': 80},
        {'sku': 'GOM-003', 'nombre': 'Gomitas de Ositos', 'stock': 200},
    ]

    context = {
        'productos': productos_ejemplo
    }
    
    return render(request, 'productos.html', context)
