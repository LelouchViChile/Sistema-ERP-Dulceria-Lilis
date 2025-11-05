# apps/users/utils_invite.py
import secrets
from django.conf import settings
from django.core.mail import send_mail

def invite_user_and_email(user):
    """
    Genera contraseña temporal + invite_code, marca must_change_password=True
    y envía correo al usuario. Devuelve la contraseña temporal generada.
    """
    # Generar credenciales temporales
    temp_password = secrets.token_urlsafe(10)[:14]  # ~14 caracteres
    code = secrets.token_hex(4).upper()             # 8 hex (A-F/0-9)

    # Setear en el usuario
    user.set_password(temp_password)
    user.invite_code = code
    user.must_change_password = True
    user.save(update_fields=["password", "invite_code", "must_change_password"])

    # Preparar correo
    nombre = (getattr(user, "get_full_name", lambda: "")() or "").strip() or user.username
    asunto = "Tu acceso a Dulcería Lilis ERP"
    cuerpo = (
        f"Hola {nombre},\n\n"
        f"Se te ha creado un acceso al ERP.\n\n"
        f"Usuario: {user.username}\n"
        f"Contraseña temporal: {temp_password}\n"
        f"Código de verificación: {code}\n\n"
        "Al iniciar sesión, se te pedirá cambiar tu contraseña y deberás ingresar ese código.\n\n"
        "Saludos,\nEquipo ERP"
    )

    send_mail(
        asunto,
        cuerpo,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )

    return temp_password
