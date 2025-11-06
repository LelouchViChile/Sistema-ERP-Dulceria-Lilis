from django.urls import path
from . import views

app_name = "suppliers"

urlpatterns = [
    path("", views.supplier_list_view, name="list"),
    path("create/", views.create_supplier, name="create"),
    path("edit/<int:supplier_id>/", views.editar_proveedor, name="edit"),
    path("delete/<int:supplier_id>/", views.eliminar_proveedor, name="delete"),
    path("relations/create/", views.create_relation, name="relations_create"),
    path("search/", views.search_suppliers, name="search"),
    path("relations/search/", views.relations_search, name="relations_search"),
    path("relations/export/", views.relations_export, name="relations_export"),
]