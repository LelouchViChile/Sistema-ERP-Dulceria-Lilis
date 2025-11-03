from django.urls import path
from . import views

# app_name ayuda a Django a diferenciar las URLs de esta app de otras.
app_name = 'products'

urlpatterns = [
    # La ruta '' (raíz dentro de la app) apunta a la vista de lista de productos.
    # El nombre 'list' se usará para referenciar esta URL, ej: {% url 'products:list' %}
    path('', views.product_list_view, name='list'),
]
