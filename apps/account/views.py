from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.urls import reverse, NoReverseMatch
from django.contrib.auth.views import PasswordResetView, PasswordResetConfirmView, PasswordChangeView
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode

import logging
logger = logging.getLogger('login_secure')  # <<<<<< YA LO TENÍAS

from django.views.decorators.cache import never_cache  # <<<<<< AGREGADO
from django.conf import settings  # <<<<<< NUEVO IMPORT

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
@never_cache  # <<<<<< AGREGADO (NO CAMBIAMOS NADA MÁS)
def iniciar_sesion(request):
    # 🔹 Mostrar mensaje de éxito si viene desde reset de contraseña: /login/?reset=1
    if request.method == "GET" and request.GET.get("reset") == "1":
        messages.success(
            request,
            "Tu contraseña ha sido actualizada correctamente. Por favor inicia sesión."
        )

    # Si ya está logueado, manda directo según rol
    if request.user.is_authenticated:
        return redirect(get_redirect_for_role(request.user))

    if request.method == "POST":
        usuario = request.POST.get("username", "")
        contrasena = request.POST.get("password", "")

        # ------------------ LOG SEGURO ------------------
        ip = request.META.get('REMOTE_ADDR', 'desconocida')
        logger.info(f"Intento de login: usuario={usuario}, ip={ip}")
        # ------------------------------------------------

        user = authenticate(request, username=usuario, password=contrasena)

        if user is not None:
            # Bloqueo de acceso si está inactivo o no-activo por negocio
            if getattr(user, "estado", "activo") != "activo" or not getattr(user, "activo", True):

                # -------- LOG BLOQUEO -----------
                logger.info(f"Login bloqueado (usuario inactivo): usuario={usuario}, ip={ip}")
                # -------------------------------

                messages.error(request, "Tu usuario está desactivado. Contacta al administrador.")
                return render(request, "login.html")

            login(request, user)

            # -------- LOG LOGIN EXITOSO --------
            logger.info(f"Login exitoso: usuario={usuario}, ip={ip}")
            # -----------------------------------

            # Solo admin/superuser respeta ?next=...; el resto va a su módulo
            next_url = request.POST.get("next") or request.GET.get("next")
            if (user.is_superuser or getattr(user, "rol", "") == "ADMIN") and next_url:
                return redirect(next_url)

            return redirect(get_redirect_for_role(user))

        # -------- LOG LOGIN FALLIDO --------
        logger.info(f"Login fallido: usuario={usuario}, ip={ip}")
        # -----------------------------------

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

    def get_context_data(self, **kwargs):
        """
        Contexto para la PÁGINA de solicitud de reset (no el correo).
        """
        context = super().get_context_data(**kwargs)

        # Dominio para mostrar en la página (no afecta al correo)
        domain = getattr(settings, "PASSWORD_RESET_DOMAIN", None) or self.request.get_host()

        protocol = getattr(settings, "PASSWORD_RESET_PROTOCOL", None)
        if not protocol:
            protocol = "https" if self.request.is_secure() else "http"

        context["domain"] = domain
        context["protocol"] = protocol
        return context

    # 🔥🔥🔥 AQUÍ ES DONDE SE ARMA EL CORREO REALMENTE 🔥🔥🔥
    def form_valid(self, form):
        """
        Sobrescribimos el envío del mail para forzar el dominio 3.85.33.49
        en el enlace de recuperación, sin romper nada más.
        """
        # Dominio fijo desde settings, con fallback a la IP por si acaso
        domain = getattr(settings, "PASSWORD_RESET_DOMAIN", "3.85.33.49")

        # Protocolo según settings o la request
        protocol = getattr(settings, "PASSWORD_RESET_PROTOCOL", None)
        use_https = (protocol == "https") or self.request.is_secure()

        # Usamos el método original de PasswordResetForm, pero pasando domain_override
        form.save(
            domain_override=domain,
            use_https=use_https,
            email_template_name=self.email_template_name,
            subject_template_name=self.subject_template_name,
            from_email=getattr(self, "from_email", None),
            request=self.request,
            html_email_template_name=getattr(self, "html_email_template_name", None),
            extra_email_context=getattr(self, "extra_email_context", None),
        )

        # Comportamiento original: redirigir a password_reset_done
        return redirect(self.success_url)


class PasswordResetConfirmCustomView(PasswordResetConfirmView):
    # Usamos tu template actual
    template_name = "password_reset_confirm.html"
    form_class = CustomSetPasswordForm
    # No tocamos dispatch, dejamos que Django maneje validlink
    
    def form_valid(self, form):
        """
        Guarda la contraseña. Si es AJAX, devuelve JSON. Si no, redirige.
        """
        user = form.save()
        logout(self.request)

        # Si la petición es AJAX (desde tu script), devuelve JSON
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            login_url = reverse("login")
            return JsonResponse({
                "ok": True,
                "redirect": f"{login_url}?reset=1"
            })

        # Comportamiento para peticiones no-AJAX (si las hubiera)
        login_url = reverse("login")
        return redirect(f"{login_url}?reset=1")

    def form_invalid(self, form):
        # Si la petición es AJAX, devuelve los errores en formato JSON
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "errors": form.errors}, status=400)
        return super().form_invalid(form)

class ChangePasswordView(PasswordChangeView):
    template_name = "change_password.html"
    form_class = CustomPasswordChangeForm

    def get_success_url(self):
        """
        Redirige al módulo que corresponde según el rol del usuario.
        """
        return get_redirect_for_role(self.request.user)

    def form_invalid(self, form):
        # Si es AJAX -> devolver errores en JSON
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "errors": form.errors}, status=400)
        return super().form_invalid(form)

    def form_valid(self, form):
        """
        Si es AJAX, devolvemos JSON con redirect dinámico por rol.
        Si es POST normal, usa get_success_url().
        """
        # Guardamos el usuario ANTES de la respuesta para poder modificarlo
        user = form.save()

        # Si era primer acceso forzado, desactivar flag y limpiar invite_code
        if getattr(user, "must_change_password", False):
            user.must_change_password = False
            user.invite_code = ""
            user.save(update_fields=["must_change_password", "invite_code"])

        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({
                "ok": True,
                "redirect": self.get_success_url()
            })
        
        # Para peticiones normales, la redirección la maneja la clase padre
        # que usa get_success_url()
        return super().form_valid(form)