# apps/account/forms.py
import re
from django import forms
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm, PasswordChangeForm
from django.core.exceptions import ValidationError

# ---- política de contraseñas (fuerte) ----
def validate_password_policy(p: str):
    if len(p or "") < 12:
        raise ValidationError("La contraseña debe tener al menos 12 caracteres.")
    if not re.search(r"[A-Z]", p or ""):
        raise ValidationError("Debe incluir al menos una mayúscula.")
    if not re.search(r"[a-z]", p or ""):
        raise ValidationError("Debe incluir al menos una minúscula.")
    if not re.search(r"\d", p or ""):
        raise ValidationError("Debe incluir al menos un dígito.")
    if not re.search(r"[^A-Za-z0-9]", p or ""):
        raise ValidationError("Debe incluir al menos un símbolo.")


class CustomPasswordResetForm(PasswordResetForm):
    """Puedes extender validaciones de email si lo necesitas."""
    pass


class CustomSetPasswordForm(SetPasswordForm):
    """Usada en reset/confirm."""
    def clean_new_password1(self):
        # SetPasswordForm SÍ define clean_new_password1, lo aprovechamos
        pwd = super().clean_new_password1()
        validate_password_policy(pwd)
        return pwd


class CustomPasswordChangeForm(PasswordChangeForm):
    """
    Usada en /password/change/ y soporta 'primer acceso' con invite_code.
    """
    invite_code = forms.CharField(
        required=False,
        max_length=12,
        label="Código de verificación (primer acceso)",
        help_text="Ingresa el código enviado a tu correo si es tu primer acceso."
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.get("user")
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].help_text = (
            "Mínimo 12 caracteres, con mayúscula, minúscula, dígito y símbolo."
        )
        if getattr(self.user, "must_change_password", False):
            self.fields["invite_code"].required = True

    def clean_new_password1(self):
        # NO llamamos a super() para evitar el error que viste.
        pwd = self.cleaned_data.get("new_password1")
        if not pwd:
            raise ValidationError("Debes ingresar la nueva contraseña.")
        validate_password_policy(pwd)
        return pwd

    def clean(self):
        cleaned = super().clean()
        if getattr(self.user, "must_change_password", False):
            code = (cleaned.get("invite_code") or "").strip()
            real = (getattr(self.user, "invite_code", "") or "").strip()
            if code != real:
                raise ValidationError("El código de verificación no es válido.")
        return cleaned
