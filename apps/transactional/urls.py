from django.urls import path
from . import views

app_name = 'transactional'

urlpatterns = [
    path('', views.gestion_transacciones, name='list'),
]
