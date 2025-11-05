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

    class Estados(models.TextChoices):
        ACTIVO = 'activo', _('Activo')
        INACTIVO = 'inactivo', _('Inactivo')
        BLOQUEADO = 'bloqueado', _('Bloqueado')

    # Importante: redefinimos email para evitar choques y asegurar índice en MySQL
    email = None
    email = models.EmailField(
        _("email address"),
        max_length=191,
        unique=True,        # único en BD
        blank=False         # requerido (tus vistas ya lo exigen)
    )

    telefono = models.CharField(
        "Teléfono",
        max_length=30,
        blank=True,         # opcional en formularios; en BD sigue siendo NOT NULL
        validators=[RegexValidator(r'^[0-9+()\-\s]{6,30}$', 'Teléfono inválido')]
    )

    rol = models.CharField(_("Rol"), max_length=20, choices=Roles.choices, default=Roles.VENTAS)

    # NUEVO: el estado que tu UI/vistas usan
    estado = models.CharField(
        _("Estado"),
        max_length=10,
        choices=Estados.choices,
        default=Estados.ACTIVO,
        db_index=True
    )

    area = models.CharField("Área/Unidad", max_length=120, blank=True)
    mfa_habilitado = models.BooleanField("MFA habilitado", default=False)

    # Puedes mantener este boolean si lo necesitas aparte del 'estado'
    activo = models.BooleanField("Activo", default=True)

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        indexes = [
            models.Index(fields=["username"]),
            # índice case-insensitive para búsquedas por email:
            models.Index(Upper("email"), name="user_email_upper_idx"),
            models.Index(fields=["activo"]),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(activo__in=[True, False]), name="usr_activo_bool"),
        ]
        ordering = ["username"]

    def __str__(self):
        nombre = (self.first_name + " " + self.last_name).strip()
        return f"{self.username} ({nombre})" if nombre else self.username
