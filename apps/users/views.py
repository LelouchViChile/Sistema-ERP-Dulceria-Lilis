# apps/users/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.db.models import Q
from .models import Usuario

from datetime import datetime

# ====== UTILIDAD: exportar queryset a Excel (openpyxl) ======
try:
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter
except ImportError:
    Workbook = None  # si openpyxl no está instalado, avisaremos en runtime


def _usuarios_to_excel(queryset):
    """
    Recibe un queryset de Usuario (ya filtrado/ordenado) y devuelve un HttpResponse
    con un .xlsx en memoria.
    """
    if Workbook is None:
        # Levantamos un error claro para que instales openpyxl si falta.
        return HttpResponse(
            "Falta dependencia: instala openpyxl (pip install openpyxl)",
            status=500,
            content_type="text/plain; charset=utf-8",
        )

    wb = Workbook()
    ws = wb.active
    ws.title = "Usuarios"

    # Encabezados (puedes ajustar el orden/columnas a gusto)
    headers = [
        "ID", "Username", "Email", "Nombre", "Apellido",
        "Teléfono", "Rol", "Estado", "MFA", "Activo",
        "Último acceso", "Creado"
    ]
    ws.append(headers)

    # Filas
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
            u.date_joined.strftime("%d/%m/%Y %H:%M") if u.date_joined else "",
        ])

    # Auto ancho simple
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            try:
                max_len = max(max_len, len(str(cell.value)) if cell.value else 0)
            except Exception:
                pass
        ws.column_dimensions[col_letter].width = min(max_len + 2, 50)

    # Respuesta HTTP con el archivo en memoria
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    filename = f"usuarios_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


@login_required
def gestion_usuarios(request):
    # Obtener parámetros de búsqueda y ordenamiento
    query = request.GET.get('q', '')
    sort_by = request.GET.get('sort', 'id')  # Ordenar por ID por defecto
    export = request.GET.get('export')       # si viene 'xlsx', exportamos

    # Lista de campos válidos para ordenar para evitar inyección
    valid_sort_fields = ['id', '-id', 'username', '-username', 'first_name', '-first_name', 'rol', '-rol']
    if sort_by not in valid_sort_fields:
        sort_by = 'id'

    # Empezar con todos los usuarios y ordenar
    usuarios_list = Usuario.objects.all().order_by(sort_by)

    # Aplicar filtro de búsqueda si existe
    if query:
        usuarios_list = usuarios_list.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query)
        )

    # Si piden exportación, devolvemos Excel del queryset filtrado/ordenado SIN paginar
    if export == 'xlsx':
        return _usuarios_to_excel(usuarios_list)

    # Configurar paginación (solo para la vista HTML)
    paginator = Paginator(usuarios_list, 10)  # 10 usuarios por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        'usuarios/gestion_usuarios.html',
        {'page_obj': page_obj, 'query': query, 'sort_by': sort_by}
    )


@login_required
def crear_usuario(request):
    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip()
        email = (request.POST.get('email') or '').strip()
        nombre = (request.POST.get('first_name') or '').strip()
        apellido = (request.POST.get('last_name') or '').strip()
        telefono = (request.POST.get('telefono') or '').strip()
        password = request.POST.get('password') or ''
        password2 = request.POST.get('password2') or ''
        rol = (request.POST.get('rol') or '').strip()
        estado = (request.POST.get('estado') or '').strip()
        mfa_habilitado = request.POST.get('mfa_habilitado') == 'on'  # 'on' si está marcado, None si no

        if not all([username, email, nombre, apellido, telefono, password, password2, rol, estado]):
            return JsonResponse({'status': 'error', 'message': 'Todos los campos son obligatorios.'})

        if password != password2:
            return JsonResponse({'status': 'error', 'message': 'Las contraseñas no coinciden.'})

        # Unicidad: username, email y teléfono
        if Usuario.objects.filter(username=username).exists():
            return JsonResponse({'status': 'error', 'message': 'El nombre de usuario ya existe.'})

        if Usuario.objects.filter(email=email).exists():
            return JsonResponse({'status': 'error', 'message': 'El email ya está registrado.'})

        if Usuario.objects.filter(telefono=telefono).exists():
            return JsonResponse({'status': 'error', 'message': 'El teléfono ya está registrado.'})

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
            # Errores de validadores de contraseña de Django
            return JsonResponse({'status': 'error', 'message': ' '.join(e.messages)})

    # Si no es POST, opcionalmente puedes devolver 405 (no imprescindible)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido.'}, status=405)


@login_required
@csrf_exempt
def eliminar_usuario(request, user_id):
    usuario = get_object_or_404(Usuario, id=user_id)
    usuario.delete()
    return JsonResponse({'status': 'ok', 'message': 'Usuario eliminado correctamente.'})


@login_required
@csrf_exempt
def editar_usuario(request, user_id):
    usuario = get_object_or_404(Usuario, id=user_id)

    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip()
        email    = (request.POST.get('email') or '').strip()
        nombre   = (request.POST.get('first_name') or '').strip()
        apellido = (request.POST.get('last_name') or '').strip()
        telefono = (request.POST.get('telefono') or '').strip()
        rol      = (request.POST.get('rol') or '').strip()
        estado   = (request.POST.get('estado') or '').strip()

        # Unicidad excluyendo al propio usuario
        if Usuario.objects.filter(username=username).exclude(id=usuario.id).exists():
            return JsonResponse({'status': 'error', 'message': 'El nombre de usuario ya existe.'})

        if Usuario.objects.filter(email=email).exclude(id=usuario.id).exists():
            return JsonResponse({'status': 'error', 'message': 'El email ya está registrado.'})

        if Usuario.objects.filter(telefono=telefono).exclude(id=usuario.id).exists():
            return JsonResponse({'status': 'error', 'message': 'El teléfono ya está registrado.'})

        usuario.username   = username
        usuario.email      = email
        usuario.first_name = nombre
        usuario.last_name  = apellido
        usuario.telefono   = telefono
        usuario.rol        = rol
        usuario.estado     = estado
        usuario.save()
        return JsonResponse({'status': 'ok', 'message': 'Usuario actualizado correctamente.'})

    # GET: devolver datos para el modal/alerta de edición
    return JsonResponse({
        'id': usuario.id,
        'username': usuario.username,
        'email': usuario.email,
        'first_name': usuario.first_name,
        'last_name': usuario.last_name,
        'telefono': usuario.telefono,
        'rol': usuario.rol,
        'estado': usuario.estado,
    })
