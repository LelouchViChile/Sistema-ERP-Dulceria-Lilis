from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator

class Usuario(AbstractUser):
    telefono = models.CharField(
        "Teléfono", max_length=30, blank=True,
        validators=[RegexValidator(r'^[0-9+()\-\s]{6,30}$', 'Teléfono inválido')]
    )
    area = models.CharField("Área/Unidad", max_length=120, blank=True)
    mfa_habilitado = models.BooleanField("MFA habilitado", default=False)
    activo = models.BooleanField("Activo", default=True)

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        indexes = [
            models.Index(fields=["username"]),
            models.Index(fields=["email"]),
            models.Index(fields=["activo"]),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(activo__in=[True, False]), name="usr_activo_bool"),
        ]

    def __str__(self):
        nombre = (self.first_name + " " + self.last_name).strip()
        return f"{self.username} ({nombre})" if nombre else self.username
