from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    # Listado (HTML)
    path('', views.product_list_view, name='list'),

    # Buscador AJAX (JSON, máx. 10 resultados)
    path('search/', views.search_products, name='search'),
]
