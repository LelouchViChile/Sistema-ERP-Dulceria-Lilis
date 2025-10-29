from django.shortcuts import render, redirect                      # Para mostrar plantillas HTML o redirigir a otras vistas
from django.contrib.auth import authenticate, login, logout        # Funciones para manejar autenticación de usuarios
from django.contrib import messages                                # Permite mostrar mensajes (error, éxito, etc.)
from django.contrib.auth.decorators import login_required          # Decorador que protege vistas solo para usuarios autenticados

# ==============================================================
# 🟢 VISTA DE INICIO DE SESIÓN
# ==============================================================

def iniciar_sesion(request):
    """
    Vista que maneja el inicio de sesión del usuario.
    Si el usuario envía el formulario (POST), se autentica.
    Si solo accede a la página (GET), se muestra el formulario.
    """
    # Si el usuario ya está autenticado, no le mostramos el login,
    # lo redirigimos directamente a la página principal.
    if request.user.is_authenticated:
        return redirect('dashboard')

    # Si el formulario fue enviado mediante POST (botón "Ingresar")
    if request.method == 'POST':
        # Capturamos los datos enviados desde el formulario
        usuario = request.POST['username']
        contrasena = request.POST['password']

        # Verificamos si existe un usuario con esas credenciales
        user = authenticate(request, username=usuario, password=contrasena)

        # Si el usuario existe (credenciales correctas)
        if user is not None:
            # Iniciamos la sesión del usuario (se guarda en la sesión de Django)
            login(request, user)
            # Redirigimos a la página principal (dashboard)
            return redirect('dashboard')
        else:
            # Si el usuario o la contraseña no son válidos, mostramos mensaje de error
            messages.error(request, 'Usuario o contraseña incorrectos.')

    # Si el método es GET (solo abrir la página), mostramos el formulario de login
    return render(request, 'login.html')


# ==============================================================
# 🔴 VISTA DE CIERRE DE SESIÓN
# ==============================================================

def cerrar_sesion(request):
    """
    Vista que maneja el cierre de sesión del usuario.
    Elimina los datos de la sesión actual y redirige al login.
    """
    # Cierra la sesión del usuario activo
    logout(request)  
    # Redirige a la página de inicio de sesión
    return redirect('login')  
