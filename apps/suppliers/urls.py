from django.urls import path
from . import views

app_name = 'suppliers'

urlpatterns = [
    # Ruta raíz de proveedores: /proveedores/
    path('', views.gestion_proveedores_view, name='list'),
]
