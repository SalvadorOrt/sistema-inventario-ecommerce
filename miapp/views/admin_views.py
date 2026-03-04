from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.contrib.auth.models import User
from ..models import PerfilUsuario, Bodega
from .helpers import _get_context_base
from django.views.decorators.cache import never_cache
# ---------------------------------------------------
# 1. LISTADO (CONSULTA)
# ---------------------------------------------------
@never_cache
@login_required
def perfiles_consulta(request):
    ctx = _get_context_base(request)
    if not request.user.is_superuser and not ctx.get('es_admin'):
        messages.error(request, "Acceso restringido.")
        return redirect('miapp:inicio')

    usuarios = User.objects.select_related('perfil', 'perfil__bodega').order_by('username')
    
    ctx.update({
        'usuarios': usuarios,
        'titulo': "Administración de Perfiles"
    })
    return render(request, "miapp/admin/perfiles_list.html", ctx)

# ---------------------------------------------------
# 2. CREAR NUEVO USUARIO
# ---------------------------------------------------
@never_cache
@login_required
def perfil_crear(request):
    ctx = _get_context_base(request)
    if not request.user.is_superuser and not ctx.get('es_admin'):
        return redirect('miapp:inicio')

    if request.method == 'POST':
        try:
            username = request.POST.get('username')
            email = request.POST.get('email')
            password = request.POST.get('password')
            nombres = request.POST.get('first_name')
            apellidos = request.POST.get('last_name')
            rol = request.POST.get('rol')
            bodega_id = request.POST.get('bodega')
            es_activo = request.POST.get('es_activo') == 'on'

            if User.objects.filter(username=username).exists():
                raise Exception("El nombre de usuario ya existe.")
            
            if not password:
                raise Exception("La contraseña es obligatoria.")

            with transaction.atomic():
                u = User.objects.create_user(username=username, email=email, password=password)
                u.first_name = nombres
                u.last_name = apellidos
                u.is_active = es_activo
                u.save()

                perfil, _ = PerfilUsuario.objects.get_or_create(user=u)
                perfil.rol_negocio = rol
                perfil.bodega_id = bodega_id if bodega_id else None
                perfil.save()

            messages.success(request, f"Usuario {username} creado correctamente.")
            return redirect('miapp:perfiles_consulta')

        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            # Si falla, no redirigimos para que no pierda los datos (opcional, aquí simplificado)

    # Preparar datos para el formulario
    bodegas = Bodega.objects.filter(es_activo=True)
    roles = PerfilUsuario.RolNegocio.choices

    ctx.update({
        'bodegas': bodegas,
        'roles': roles,
        'titulo': "Crear Nuevo Usuario",
        'accion': 'Crear'
    })
    return render(request, "miapp/admin/perfil_form.html", ctx)

# ---------------------------------------------------
# 3. EDITAR USUARIO EXISTENTE
# ---------------------------------------------------
@never_cache
@login_required
def perfil_editar(request, pk):
    ctx = _get_context_base(request)
    if not request.user.is_superuser and not ctx.get('es_admin'):
        return redirect('miapp:inicio')

    # Buscamos el usuario a editar
    usuario_edit = get_object_or_404(User, pk=pk)

    if request.method == 'POST':
        try:
            username = request.POST.get('username')
            email = request.POST.get('email')
            password = request.POST.get('password')
            nombres = request.POST.get('first_name')
            apellidos = request.POST.get('last_name')
            rol = request.POST.get('rol')
            bodega_id = request.POST.get('bodega')
            es_activo = request.POST.get('es_activo') == 'on'

            with transaction.atomic():
                # Validar nombre único si lo cambió
                if usuario_edit.username != username and User.objects.filter(username=username).exists():
                    raise Exception("Ese nombre de usuario ya está ocupado.")

                usuario_edit.username = username
                usuario_edit.email = email
                usuario_edit.first_name = nombres
                usuario_edit.last_name = apellidos
                usuario_edit.is_active = es_activo
                
                # Solo actualizar password si escribió algo
                if password and password.strip():
                    usuario_edit.set_password(password)
                
                usuario_edit.save()

                # Actualizar Perfil
                perfil, _ = PerfilUsuario.objects.get_or_create(user=usuario_edit)
                perfil.rol_negocio = rol
                perfil.bodega_id = bodega_id if bodega_id else None
                perfil.save()

            messages.success(request, f"Usuario {username} actualizado correctamente.")
            return redirect('miapp:perfiles_consulta')

        except Exception as e:
            messages.error(request, f"Error: {str(e)}")

    # Preparar datos para el formulario (rellenar con datos actuales)
    bodegas = Bodega.objects.filter(es_activo=True)
    roles = PerfilUsuario.RolNegocio.choices

    ctx.update({
        'usuario_obj': usuario_edit, # Pasamos el objeto para llenar los campos en HTML
        'bodegas': bodegas,
        'roles': roles,
        'titulo': f"Editar Usuario: {usuario_edit.username}",
        'accion': 'Guardar Cambios'
    })
    return render(request, "miapp/admin/perfil_form.html", ctx)