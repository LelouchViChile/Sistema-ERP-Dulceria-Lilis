from django.urls import path
from . import views

app_name = "suppliers"

urlpatterns = [
    # Página principal
    path("", views.supplier_list_view, name="list"),

    # CRUD AJAX
    path("create/", views.create_supplier, name="create"),
    path("relations/create/", views.create_relation, name="relations_create"),

    # Buscadores AJAX (máx. 10)
    path("search/", views.search_suppliers, name="search"),
    path("relations/search/", views.relations_search, name="relations_search"),

    # Export
    path("relations/export/", views.relations_export, name="relations_export"),
]
