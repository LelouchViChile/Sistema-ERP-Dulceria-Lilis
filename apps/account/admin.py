from django.contrib import admin
from .models import Perfil

@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ("usuario", "cargo", "avatar_url")
    search_fields = ("usuario__username", "usuario__email", "cargo")
