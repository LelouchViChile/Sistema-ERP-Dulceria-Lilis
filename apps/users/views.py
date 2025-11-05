# apps/users/views.py
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404

from .models import Usuario

# ====== Exportar a Excel (openpyxl) ======
try:
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter
except ImportError:
    Workbook = None


def _usuarios_to_excel(queryset):
    """Devuelve un HttpResponse con un .xlsx generado en memoria."""
    if Workbook is None:
        return HttpResponse(
            "Falta dependencia: instala openpyxl (pip install openpyxl)",
            status=500,
            content_type="text/plain; charset=utf-8",
        )

    wb = Workbook()
    ws = wb.active
    ws.title = "Usuarios"

    headers = [
        "ID", "Username", "Email", "Nombre", "Apellido",
        "Teléfono", "Rol", "Estado", "MFA", "Activo",
        "Último acceso", "Creado"
    ]
    ws.append(headers)

    for u in queryset:
        ws.append([
            u.id,
            u.username,
            u.email,
            u.first_name or "",
            u.last_name or "",
            u.telefono or "",
            getattr(u, "rol", ""),
            getattr(u, "estado", ""),
            "Sí" if getattr(u, "mfa_habilitado", False) else "No",
            "Sí" if getattr(u, "activo", False) else "No",
            u.last_login.strftime("%d/%m/%Y %H:%M") if u.last_login else "",
            u.date_joined.strftime("%d/%m/%Y %H:%M") if getattr(u, "date_joined", None) else "",
        ])

    # Auto ancho sencillo
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            try:
                max_len = max(max_len, len(str(cell.value)) if cell.value else 0)
            except Exception:
                pass
        ws.column_dimensions[col_letter].width = min(max_len + 2, 50)

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    filename = f"usuarios_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


@login_required
def gestion_usuarios(request):
    """Listado con búsqueda, orden, paginación y exportación."""
    query = request.GET.get('q', '')
    sort_by = request.GET.get('sort', 'id')
    export = request.GET.get('export')

    valid_sort_fields = ['id', '-id', 'username', '-username', 'first_name', '-first_name', 'rol', '-rol']
    if sort_by not in valid_sort_fields:
        sort_by = 'id'

    usuarios_list = Usuario.objects.all().order_by(sort_by)

    if query:
        usuarios_list = usuarios_list.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query) |
            Q(rol__icontains=query) |
            Q(estado__icontains=query)
        )

    if export == 'xlsx':
        return _usuarios_to_excel(usuarios_list)

    paginator = Paginator(usuarios_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        'usuarios/gestion_usuarios.html',
        {'page_obj': page_obj, 'query': query, 'sort_by': sort_by}
    )


@login_required
def crear_usuario(request):
    """Alta por fetch: devuelve JSON."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido.'}, status=405)

    username = (request.POST.get('username') or '').strip()
    email = (request.POST.get('email') or '').strip()
    nombre = (request.POST.get('first_name') or '').strip()
    apellido = (request.POST.get('last_name') or '').strip()
    telefono = (request.POST.get('telefono') or '').strip()
    password = request.POST.get('password') or ''
    password2 = request.POST.get('password2') or ''
    rol = (request.POST.get('rol') or '').strip()
    estado = (request.POST.get('estado') or '').strip()
    mfa_habilitado_raw = request.POST.get('mfa_habilitado') or ''
    # En el form llega "Si"/"No"
    mfa_habilitado = True if mfa_habilitado_raw.lower() in ('si', 'sí', 'true', '1', 'on') else False

    # Requeridos
    if not all([username, email, nombre, apellido, telefono, password, password2, rol, estado]):
        return JsonResponse({'status': 'error', 'message': 'Todos los campos son obligatorios.'}, status=400)

    if password != password2:
        return JsonResponse({'status': 'error', 'message': 'Las contraseñas no coinciden.'}, status=400)

    # Duplicados
    if Usuario.objects.filter(username=username).exists():
        return JsonResponse({'status': 'error', 'message': 'El nombre de usuario ya existe.'}, status=400)
    if Usuario.objects.filter(email=email).exists():
        return JsonResponse({'status': 'error', 'message': 'El email ya está registrado.'}, status=400)
    if Usuario.objects.filter(telefono=telefono).exists():
        return JsonResponse({'status': 'error', 'message': 'El teléfono ya está registrado.'}, status=400)

    try:
        usuario = Usuario.objects.create_user(
            username=username,
            email=email,
            first_name=nombre,
            last_name=apellido,
            telefono=telefono,
            rol=rol,
            estado=estado,
            password=password,
            mfa_habilitado=mfa_habilitado
        )
        usuario.save()
        return JsonResponse({'status': 'ok', 'message': 'Usuario creado correctamente.'})
    except ValidationError as e:
        return JsonResponse({'status': 'error', 'message': ' '.join(e.messages)}, status=400)


@login_required
def eliminar_usuario(request, user_id):
    """Baja por fetch (POST) -> JSON."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido.'}, status=405)
    usuario = get_object_or_404(Usuario, id=user_id)
    usuario.delete()
    return JsonResponse({'status': 'ok', 'message': 'Usuario eliminado correctamente.'})


@login_required
def editar_usuario(request, user_id):
    """
    GET: devuelve datos del usuario {status:'ok', user:{...}} para poblar el modal.
    POST: actualiza. Valida duplicados (username/email/telefono) excluyendo el propio id.
    Permite cambiar contraseña (opcional, si viene y tiene 8+).
    """
    usuario = get_object_or_404(Usuario, id=user_id)

    if request.method == 'GET':
        return JsonResponse({
            'status': 'ok',
            'user': {
                'id': usuario.id,
                'username': usuario.username,
                'email': usuario.email or '',
                'first_name': usuario.first_name or '',
                'last_name': usuario.last_name or '',
                'telefono': usuario.telefono or '',
                'rol': getattr(usuario, 'rol', '') or '',
                'estado': getattr(usuario, 'estado', '') or '',
                'mfa_habilitado': bool(getattr(usuario, 'mfa_habilitado', False)),
            }
        })

    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido.'}, status=405)

    username = (request.POST.get('username') or '').strip()
    email = (request.POST.get('email') or '').strip()
    first_name = (request.POST.get('first_name') or '').strip()
    last_name = (request.POST.get('last_name') or '').strip()
    telefono = (request.POST.get('telefono') or '').strip()
    rol = (request.POST.get('rol') or '').strip()
    estado = (request.POST.get('estado') or '').strip()
    new_password = (request.POST.get('password') or '').strip()

    # Requeridos mínimos
    if not username or not email:
        return JsonResponse({'status': 'error', 'message': 'Username y email son obligatorios.'}, status=400)

    # Duplicados excluyéndose a sí mismo
    if Usuario.objects.filter(username=username).exclude(id=user_id).exists():
        return JsonResponse({'status': 'error', 'message': 'El nombre de usuario ya existe.'}, status=400)
    if Usuario.objects.filter(email=email).exclude(id=user_id).exists():
        return JsonResponse({'status': 'error', 'message': 'El email ya está registrado.'}, status=400)
    if telefono and Usuario.objects.filter(telefono=telefono).exclude(id=user_id).exists():
        return JsonResponse({'status': 'error', 'message': 'El teléfono ya está registrado.'}, status=400)

    # Actualiza
    usuario.username = username
    usuario.email = email
    usuario.first_name = first_name
    usuario.last_name = last_name
    usuario.telefono = telefono
    if rol:
        usuario.rol = rol
    if estado:
        usuario.estado = estado

    # Password opcional
    if new_password:
        if len(new_password) < 8:
            return JsonResponse({'status': 'error', 'message': 'La nueva contraseña debe tener al menos 8 caracteres.'}, status=400)
        usuario.set_password(new_password)

    usuario.save()
    return JsonResponse({'status': 'ok', 'message': 'Usuario actualizado correctamente.'})
