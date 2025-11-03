from django.urls import path
from . import views  # Importamos las vistas de este módulo

urlpatterns = [
    # Ruta para iniciar sesión
    path('login/', views.iniciar_sesion, name='login'),

    # Ruta para cerrar sesión
    path('logout/', views.cerrar_sesion, name='logout'),
]
