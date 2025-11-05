from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.urls import reverse, NoReverseMatch

def safe_reverse(*candidates, default="dashboard"):
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

def iniciar_sesion(request):
    # Si ya está logueado, manda directo según rol
    if request.user.is_authenticated:
        return redirect(get_redirect_for_role(request.user))

    if request.method == "POST":
        usuario = request.POST.get("username", "")
        contrasena = request.POST.get("password", "")
        user = authenticate(request, username=usuario, password=contrasena)

        if user is not None:
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
