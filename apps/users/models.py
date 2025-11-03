# users/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models

class Usuario(AbstractUser):
    ROLES = [
        ('ADMIN', 'Administrador'),
        ('USER', 'Usuario'),
        ('SUPERVISOR', 'Supervisor'),
        ('AUDITOR', 'Auditor'),
        ('OPERADOR', 'Operador'),
    ]

    ESTADOS = [
        ('activo', 'Activo'),
        ('inactivo', 'Inactivo'),
        ('bloqueado', 'Bloqueado'),
    ]

    telefono = models.CharField(max_length=20, blank=True, null=True)
    rol = models.CharField(max_length=20, choices=ROLES, default='USER')
    estado = models.CharField(max_length=20, choices=ESTADOS, default='activo')
    mfa_habilitado = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.username} ({self.rol})"
