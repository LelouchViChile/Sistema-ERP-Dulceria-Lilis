# users/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.db.models import Q
from .models import Usuario

@login_required
def gestion_usuarios(request):
    # Obtener parámetros de búsqueda y ordenamiento
    query = request.GET.get('q', '')
    sort_by = request.GET.get('sort', 'id') # Ordenar por ID por defecto

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

    # Configurar paginación
    paginator = Paginator(usuarios_list, 10) # 10 usuarios por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'usuarios/gestion_usuarios.html', {'page_obj': page_obj, 'query': query, 'sort_by': sort_by})


@login_required
def crear_usuario(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        nombre = request.POST.get('first_name')
        apellido = request.POST.get('last_name')
        telefono = request.POST.get('telefono')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        rol = request.POST.get('rol')
        estado = request.POST.get('estado')
        mfa_habilitado = request.POST.get('mfa_habilitado') == 'on' # 'on' si está marcado, None si no

        if not all([username, email, nombre, apellido, telefono, password, password2, rol, estado]):
            return JsonResponse({'status': 'error', 'message': 'Todos los campos son obligatorios.'})

        if Usuario.objects.filter(username=username).exists():
            return JsonResponse({'status': 'error', 'message': 'El nombre de usuario ya existe.'})

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
            # Capturamos los errores de los validadores de contraseña de Django
            # y los enviamos como una respuesta de error clara.
            return JsonResponse({'status': 'error', 'message': ' '.join(e.messages)})



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
        usuario.username = request.POST.get('username')
        usuario.email = request.POST.get('email')
        usuario.first_name = request.POST.get('first_name')
        usuario.last_name = request.POST.get('last_name')
        usuario.telefono = request.POST.get('telefono')
        usuario.rol = request.POST.get('rol')
        usuario.estado = request.POST.get('estado')
        usuario.save()
        return JsonResponse({'status': 'ok', 'message': 'Usuario actualizado correctamente.'})

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
