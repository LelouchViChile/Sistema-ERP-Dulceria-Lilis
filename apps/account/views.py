# apps/account/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.urls import reverse, NoReverseMatch
from django.contrib.auth.views import PasswordResetView, PasswordResetConfirmView, PasswordChangeView
from django.urls import reverse_lazy

from .forms import (
    CustomPasswordResetForm,
    CustomSetPasswordForm,
    CustomPasswordChangeForm,
)

# ------------------ utilidades ------------------
def safe_reverse(*candidates, default="dashboard"):
    """
    Intenta hacer reverse de varios nombres; si ninguno existe, usa `default`,
    y si tampoco existe, retorna "/".
    """
    for name in candidates:
        try:
            return reverse(name)
        except NoReverseMatch:
            continue
    try:
        return reverse(default)
    except NoReverseMatch:
        return "/"


def get_redirect_for_role(user):
    rol = getattr(user, "rol", "") or ""

    # Admin / superuser → dashboard
    if user.is_superuser or rol == "ADMIN":
        return safe_reverse("dashboard")

    # Resto de roles → su módulo
    role_map = {
        "COMPRAS":     ("suppliers:list", "gestion_proveedores"),
        "INVENTARIO":  ("products:list", "product_list"),
        "VENTAS":      ("products:list", "product_list"),
        "PRODUCCION":  ("transactional:list", "gestion_transacciones"),
        "FINANZAS":    ("reports:panel",),
    }
    candidates = role_map.get(rol, ("dashboard",))
    return safe_reverse(*candidates, default="dashboard")


# ------------------ auth views ------------------
def iniciar_sesion(request):
    # Si ya está logueado, manda directo según rol
    if request.user.is_authenticated:
        return redirect(get_redirect_for_role(request.user))

    if request.method == "POST":
        usuario = request.POST.get("username", "")
        contrasena = request.POST.get("password", "")
        user = authenticate(request, username=usuario, password=contrasena)

        if user is not None:
            # Bloqueo de acceso si está inactivo o no-activo por negocio
            if getattr(user, "estado", "activo") != "activo" or not getattr(user, "activo", True):
                messages.error(request, "Tu usuario está desactivado. Contacta al administrador.")
                return render(request, "login.html")

            login(request, user)

            # Solo admin/superuser respeta ?next=...; el resto va a su módulo
            next_url = request.POST.get("next") or request.GET.get("next")
            if (user.is_superuser or getattr(user, "rol", "") == "ADMIN") and next_url:
                return redirect(next_url)

            return redirect(get_redirect_for_role(user))

        messages.error(request, "Usuario o contraseña incorrectos.")

    return render(request, "login.html")  # incluye {% csrf_token %} y el <input name="next">


def cerrar_sesion(request):
    logout(request)
    return redirect("login")


@login_required
def module_gate_view(request, app_slug: str):
    return render(request, "module_gate.html", {"app_slug": app_slug})


# ------------------ password reset / change ------------------
class PasswordResetRequestView(PasswordResetView):
    template_name = "password_reset_request.html"
    email_template_name = "emails/password_reset_email.txt"
    subject_template_name = "emails/password_reset_subject.txt"
    success_url = reverse_lazy("password_reset_done")
    form_class = CustomPasswordResetForm


class PasswordResetConfirmCustomView(PasswordResetConfirmView):
    template_name = "password_rest_confirm.html"  # tu nombre exacto
    form_class = CustomSetPasswordForm
    success_url = reverse_lazy("password_reset_complete")


class ChangePasswordView(PasswordChangeView):
    template_name = "change_password.html"  # usaremos tu template extendido
    form_class = CustomPasswordChangeForm
    success_url = reverse_lazy("password_change_done")

    def form_valid(self, form):
        resp = super().form_valid(form)
        u = self.request.user
        # Si era primer acceso forzado, limpiar flags
        if getattr(u, "must_change_password", False):
            u.must_change_password = False
            u.invite_code = ""
            u.save(update_fields=["must_change_password", "invite_code"])
        return resp
