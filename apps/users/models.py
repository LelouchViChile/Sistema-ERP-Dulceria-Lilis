from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Upper
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _

class Usuario(AbstractUser):
    class Roles(models.TextChoices):
        ADMIN = 'ADMIN', _('Administrador')
        COMPRAS = 'COMPRAS', _('Operador de Compras')
        INVENTARIO = 'INVENTARIO', _('Operador de Inventario')
        PRODUCCION = 'PRODUCCION', _('Operador de Producción')
        VENTAS = 'VENTAS', _('Operador de Ventas')
        FINANZAS = 'FINANZAS', _('Analista Financiero')

    # Anulamos el campo 'email' del modelo base AbstractUser para evitar conflictos.
    email = None
    # Definimos nuestro propio campo de email con una longitud segura para los índices de MySQL.
    email = models.EmailField(
        _("email address"), max_length=191, unique=True, blank=True
    )
    telefono = models.CharField(
        "Teléfono", max_length=30, blank=True,
        validators=[RegexValidator(r'^[0-9+()\-\s]{6,30}$', 'Teléfono inválido')]
    )
    rol = models.CharField(_("Rol"), max_length=20, choices=Roles.choices, default=Roles.VENTAS)
    area = models.CharField("Área/Unidad", max_length=120, blank=True)
    mfa_habilitado = models.BooleanField("MFA habilitado", default=False)
    activo = models.BooleanField("Activo", default=True)

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        indexes = [
            models.Index(fields=["username"]),
            models.Index(Upper("email"), name="user_email_upper_idx"), # Índice case-insensitive para búsquedas eficientes
            models.Index(fields=["activo"]),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(activo__in=[True, False]), name="usr_activo_bool"),
        ]

    def __str__(self):
        nombre = (self.first_name + " " + self.last_name).strip()
        return f"{self.username} ({nombre})" if nombre else self.username
