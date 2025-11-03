"""
URL configuration for lilis_erp project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from . import views # Importamos las vistas del proyecto

urlpatterns = [
    # --- Ruta Principal ---
    # La URL raíz ('/') apunta a la vista 'dashboard_page'.
    # Como 'dashboard_page' está protegida, redirigirá automáticamente a 'login' si no has iniciado sesión.
    # Esta ruta DEBE ir primero.
    path('', views.dashboard_page, name='dashboard'),

    path('admin/', admin.site.urls),

    # --- Rutas de Autenticación ---
    # Incluimos las URLs de la app 'account' ('/login/', '/logout/') en la raíz.
    path('', include('apps.account.urls')),

    # --- Rutas de Productos ---
    # Todas las URLs que comiencen con 'productos/' serán manejadas por la app 'products'.
    path('productos/', include('apps.products.urls')),

    # --- Rutas de Usuarios ---
    # Todas las URLs que comiencen con 'users/' serán manejadas por la app 'users'.
    path('users/', include('apps.users.urls')),

    # --- Rutas de Proveedores ---
    # Todas las URLs que comiencen con 'proveedores/' serán manejadas por la app 'suppliers'.
    path('proveedores/', include('apps.suppliers.urls')),

    # --- Rutas de Transacciones ---
    path('transacciones/', include('apps.transactional.urls')),
]
