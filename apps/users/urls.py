from django.urls import path
from . import views

urlpatterns = [
    path("", views.gestion_usuarios, name="gestion_usuarios"),
    path("crear/", views.crear_usuario, name="crear_usuario"),
    path("editar/<int:pk>/", views.editar_usuario, name="editar_usuario"),
    path("eliminar/<int:pk>/", views.eliminar_usuario, name="eliminar_usuario"),
]
