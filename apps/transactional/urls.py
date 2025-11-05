from django.urls import path
from . import views

app_name = 'transactional'

urlpatterns = [
    path('', views.gestion_transacciones, name='list'),
    # Buscador AJAX: máx. 10
    path('search/', views.search_transactions, name='search'),
]
