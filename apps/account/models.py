from django.db import models
from django.conf import settings

class Perfil(models.Model):
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil", verbose_name="Usuario")
    cargo = models.CharField("Cargo", max_length=120, blank=True)
    avatar_url = models.URLField("Avatar (URL)", blank=True)

    class Meta:
        verbose_name = "Perfil"
        verbose_name_plural = "Perfiles"

    def __str__(self):
        return f"Perfil de {self.usuario.username}"
