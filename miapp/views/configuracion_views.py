# Django
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q, Count

# Helpers
from .helpers import requiere_admin_negocio, _get_context_base

# Modelos
from ..models import (
    Impuesto,
    TipoAlmacenamiento,
    TipoIdentificacion,
    ClaseProducto,
    PerfilCaducidad,
    EstadoLote,
    TipoMovimiento,
    EstadoPedido,
    Pais,
)

# Formularios
from ..forms.configuracion_forms import (
    ImpuestoForm,
    TipoAlmacenamientoForm,
    TipoIdentificacionForm,
    ClaseProductoForm,
    PerfilCaducidadForm,
    EstadoLoteForm,
    TipoMovimientoForm,
    EstadoPedidoForm,
    PaisForm,
)

# ============================================================
# PANEL GENERAL DE CONFIGURACIÓN
# ============================================================

@login_required
@requiere_admin_negocio
def configuracion_panel(request):
    """Vista para el menú visual de configuración"""
    ctx = _get_context_base(request)
    ctx.update({
        "titulo": "Panel de Configuración"
    })
    return render(request, "miapp/configuracion/panel_general.html", ctx)

# ============================================================
# GESTIÓN DE IMPUESTOS (IVA)
# ============================================================

@login_required
@requiere_admin_negocio
def impuestos_list(request):
    # 1. Cargar contexto base para no perder el menú lateral
    ctx = _get_context_base(request)
    
    # 2. Captura de filtros
    q = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "")
    
    filtros = Q()
    if q:
        filtros &= Q(nombre__icontains=q)
    
    if estado == 'activos':
        filtros &= Q(es_activo=True)
    elif estado == 'inactivos':
        filtros &= Q(es_activo=False)

    # 3. Consulta (Ordenamos por nombre)
    items = Impuesto.objects.filter(filtros).order_by('nombre')

    ctx.update({
        "items": items,
        "q": q,
        "estado": estado,
        "titulo": "Gestión de Impuestos"
    })
    return render(request, "miapp/configuracion/impuestos_list.html", ctx)

@login_required
@requiere_admin_negocio
def impuesto_crear(request):
    return _procesar_impuesto(request, pk=None)

@login_required
@requiere_admin_negocio
def impuesto_editar(request, pk):
    return _procesar_impuesto(request, pk=pk)

def _procesar_impuesto(request, pk):
    ctx = _get_context_base(request)
    instance = get_object_or_404(Impuesto, pk=pk) if pk else None
    modo = "Editar" if pk else "Crear"
    
    if request.method == "POST":
        form = ImpuestoForm(request.POST, instance=instance)
        if form.is_valid():
            imp = form.save()
            messages.success(request, f"Impuesto '{imp.nombre}' guardado correctamente.")
            return redirect("miapp:impuestos_gestion")
        else:
            messages.error(request, "Por favor corrige los errores del formulario.")
    else:
        form = ImpuestoForm(instance=instance, initial={'es_activo': True} if not pk else None)

    ctx.update({
        "form": form,
        "modo": modo,
        "titulo": f"{modo} Impuesto"
    })
    return render(request, "miapp/configuracion/impuesto_form.html", ctx)


# ============================================================
# GESTIÓN DE TIPOS DE ALMACENAMIENTO
# ============================================================

@login_required
@requiere_admin_negocio
def tipos_almacenamiento_list(request):
    ctx = _get_context_base(request)
    
    q = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "activos")
    
    filtros = Q()
    if q:
        filtros &= (Q(codigo__icontains=q) | Q(descripcion__icontains=q))
    
    if estado == 'activos':
        filtros &= Q(es_activo=True)
    elif estado == 'inactivos':
        filtros &= Q(es_activo=False)

    # Annotate para ver cuántas zonas o productos usan este tipo
    items = TipoAlmacenamiento.objects.filter(filtros).annotate(
        num_zonas=Count('zonas', filter=Q(zonas__es_activo=True)),
        num_productos=Count('productos', filter=Q(productos__es_activo=True))
    ).order_by('codigo')

    ctx.update({
        "items": items,
        "q": q,
        "estado": estado,
        "titulo": "Tipos de Almacenamiento"
    })
    return render(request, "miapp/configuracion/tipo_almacenamiento_list.html", ctx)

@login_required
@requiere_admin_negocio
def tipo_almacenamiento_crear(request):
    return _procesar_tipo_almacenamiento(request, pk=None)

@login_required
@requiere_admin_negocio
def tipo_almacenamiento_editar(request, pk):
    return _procesar_tipo_almacenamiento(request, pk=pk)

def _procesar_tipo_almacenamiento(request, pk):
    ctx = _get_context_base(request)
    instance = get_object_or_404(TipoAlmacenamiento, pk=pk) if pk else None
    modo = "Editar" if pk else "Crear"
    
    if request.method == "POST":
        form = TipoAlmacenamientoForm(request.POST, instance=instance)
        if form.is_valid():
            # Capturamos el nuevo estado del checkbox
            nuevo_estado = form.cleaned_data.get('es_activo')
            
            # REGLA: Si el registro estaba ACTIVO y el usuario lo quiere DESACTIVAR (False)
            if instance and instance.es_activo and not nuevo_estado:
                # 1. Verificar si existen Zonas vinculadas (activas o no, por integridad)
                # Nota: Si no definiste related_name en el modelo, usa 'zona_set'
                tiene_zonas = instance.zonas.exists() 
                
                # 2. Verificar si existen Productos vinculados
                tiene_productos = instance.productos.exists()

                if tiene_zonas or tiene_productos:
                    messages.error(request, 
                        f"No se puede desactivar: Este tipo de almacenamiento está siendo utilizado por "
                        f"{'zonas' if tiene_zonas else ''} {'y productos' if tiene_productos else ''}."
                    )
                    # Recargamos el contexto y devolvemos el formulario con el error
                    ctx.update({"form": form, "modo": modo, "titulo": f"{modo} Tipo"})
                    return render(request, "miapp/configuracion/tipo_almacenamiento_form.html", ctx)

            # Si pasa la validación, guardamos
            item = form.save()
            messages.success(request, f"Tipo '{item.codigo}' guardado correctamente.")
            return redirect("miapp:tipos_almacenamiento_gestion")
        else:
            messages.error(request, "Verifique los datos ingresados.")
    else:
        form = TipoAlmacenamientoForm(instance=instance, initial={'es_activo': True} if not pk else None)

    ctx.update({
        "form": form,
        "modo": modo,
        "titulo": f"{modo} Tipo de Almacenamiento"
    })
    return render(request, "miapp/configuracion/tipo_almacenamiento_form.html", ctx)


# ============================================================
# GESTIÓN DE TIPOS DE IDENTIFICACIÓN
# ============================================================

@login_required
@requiere_admin_negocio
def tipos_identificacion_list(request):
    ctx = _get_context_base(request)
    
    q = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "activos")
    
    filtros = Q()
    if q:
        filtros &= (Q(codigo__icontains=q) | Q(descripcion__icontains=q))
    
    if estado == 'activos':
        filtros &= Q(es_activo=True)
    elif estado == 'inactivos':
        filtros &= Q(es_activo=False)

    # CORRECCIÓN: Se usa 'proveedores' y 'clientes' en plural
    items = TipoIdentificacion.objects.filter(filtros).annotate(
        num_proveedores=Count('proveedores', filter=Q(proveedores__es_activo=True)),
        num_clientes=Count('clientes', filter=Q(clientes__es_activo=True))
    ).order_by('codigo')

    ctx.update({
        "items": items,
        "q": q,
        "estado": estado,
        "titulo": "Tipos de Identificación"
    })
    return render(request, "miapp/configuracion/tipo_identificacion_list.html", ctx)

@login_required
@requiere_admin_negocio
def tipo_identificacion_crear(request):
    return _procesar_tipo_identificacion(request, pk=None)

@login_required
@requiere_admin_negocio
def tipo_identificacion_editar(request, pk):
    return _procesar_tipo_identificacion(request, pk=pk)

def _procesar_tipo_identificacion(request, pk):
    ctx = _get_context_base(request)
    instance = get_object_or_404(TipoIdentificacion, pk=pk) if pk else None
    modo = "Editar" if pk else "Crear"
    
    if request.method == "POST":
        form = TipoIdentificacionForm(request.POST, instance=instance)
        if form.is_valid():
            nuevo_estado = form.cleaned_data.get('es_activo')
            if instance and instance.es_activo and not nuevo_estado:
                # CORRECCIÓN: Usar los nombres de relación correctos
                en_uso_prov = instance.proveedores.exists()
                en_uso_cli = instance.clientes.exists()
                
                if en_uso_prov or en_uso_cli:
                    messages.error(request, "No se puede desactivar: Este tipo ya está asignado a clientes o proveedores.")
                    ctx.update({"form": form, "modo": modo, "titulo": f"{modo} Tipo"})
                    return render(request, "miapp/configuracion/tipo_identificacion_form.html", ctx)

            item = form.save()
            messages.success(request, f"Tipo '{item.codigo}' guardado correctamente.")
            return redirect("miapp:tipos_identidad_gestion")
    else:
        form = TipoIdentificacionForm(instance=instance, initial={'es_activo': True} if not pk else None)

    ctx.update({
        "form": form,
        "modo": modo,
        "titulo": f"{modo} Tipo de Identificación"
    })
    return render(request, "miapp/configuracion/tipo_identificacion_form.html", ctx)

# ============================================================
# GESTIÓN DE CLASES DE PRODUCTO
# ============================================================

@login_required
@requiere_admin_negocio
def clases_producto_list(request):
    ctx = _get_context_base(request)
    
    q = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "activos")
    
    filtros = Q()
    if q:
        filtros &= (Q(codigo__icontains=q) | Q(descripcion__icontains=q))
    
    if estado == 'activos':
        filtros &= Q(es_activo=True)
    elif estado == 'inactivos':
        filtros &= Q(es_activo=False)

    # Contamos cuántos productos usan esta clase (relación inversa: productos)
    items = ClaseProducto.objects.filter(filtros).annotate(
        num_productos=Count('productos', filter=Q(productos__es_activo=True))
    ).order_by('codigo')

    ctx.update({
        "items": items,
        "q": q,
        "estado": estado,
        "titulo": "Clases de Producto"
    })
    return render(request, "miapp/configuracion/clase_producto_list.html", ctx)

@login_required
@requiere_admin_negocio
def clase_producto_crear(request):
    return _procesar_clase_producto(request, pk=None)

@login_required
@requiere_admin_negocio
def clase_producto_editar(request, pk):
    return _procesar_clase_producto(request, pk=pk)

def _procesar_clase_producto(request, pk):
    ctx = _get_context_base(request)
    instance = get_object_or_404(ClaseProducto, pk=pk) if pk else None
    modo = "Editar" if pk else "Crear"
    
    if request.method == "POST":
        form = ClaseProductoForm(request.POST, instance=instance)
        if form.is_valid():
            # Validación: No desactivar si tiene productos activos
            nuevo_estado = form.cleaned_data.get('es_activo')
            if instance and instance.es_activo and not nuevo_estado:
                tiene_productos = instance.productos.filter(es_activo=True).exists()
                if tiene_productos:
                    messages.error(request, "No se puede desactivar: Esta clase está asignada a productos activos.")
                    ctx.update({"form": form, "modo": modo, "titulo": f"{modo} Clase"})
                    return render(request, "miapp/configuracion/clase_producto_form.html", ctx)

            item = form.save()
            messages.success(request, f"Clase '{item.codigo}' guardada correctamente.")
            return redirect("miapp:clases_producto_gestion")
    else:
        form = ClaseProductoForm(instance=instance, initial={'es_activo': True} if not pk else None)

    ctx.update({
        "form": form,
        "modo": modo,
        "titulo": f"{modo} Clase de Producto"
    })
    return render(request, "miapp/configuracion/clase_producto_form.html", ctx)




# ============================================================
# GESTIÓN DE PERFILES DE CADUCIDAD
# ============================================================
@login_required
@requiere_admin_negocio
def perfiles_caducidad_list(request):
    ctx = _get_context_base(request)
    
    q = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "activos")
    
    filtros = Q()
    if q:
        filtros &= (Q(codigo__icontains=q) | Q(descripcion__icontains=q))
    
    if estado == 'activos':
        filtros &= Q(es_activo=True)
    elif estado == 'inactivos':
        filtros &= Q(es_activo=False)

    # Obtenemos los perfiles y contamos cuántos productos los usan
    items = PerfilCaducidad.objects.filter(filtros).annotate(
        num_productos=Count('productos', filter=Q(productos__es_activo=True))
    ).order_by('codigo')

    ctx.update({
        "items": items,
        "q": q,
        "estado": estado,
        "titulo": "Perfiles de Caducidad"
    })
    return render(request, "miapp/configuracion/perfil_caducidad_list.html", ctx)

@login_required
@requiere_admin_negocio
def perfil_caducidad_crear(request):
    return _procesar_perfil_caducidad(request, pk=None)

@login_required
@requiere_admin_negocio
def perfil_caducidad_editar(request, pk):
    return _procesar_perfil_caducidad(request, pk=pk)

def _procesar_perfil_caducidad(request, pk):
    ctx = _get_context_base(request)
    instance = get_object_or_404(PerfilCaducidad, pk=pk) if pk else None
    modo = "Editar" if pk else "Crear"
    
    if request.method == "POST":
        form = PerfilCaducidadForm(request.POST, instance=instance)
        if form.is_valid():
            try:
                item = form.save()
                messages.success(request, f"Perfil '{item.codigo}' guardado correctamente.")
                return redirect("miapp:perfiles_caducidad_gestion")
            except ValidationError as e:
                # Esto atrapa errores lanzados desde el modelo o clean()
                messages.error(request, str(e))
        else:
            messages.error(request, "Por favor revise las inconsistencias en el formulario.")
    else:
        form = PerfilCaducidadForm(instance=instance, initial={'es_activo': True} if not pk else None)

    ctx.update({"form": form, "modo": modo, "titulo": f"{modo} Perfil de Caducidad"})
    return render(request, "miapp/configuracion/perfil_caducidad_form.html", ctx)


# ============================================================
# GESTIÓN DE ESTADOS DE LOTE
# ============================================================

@login_required
@requiere_admin_negocio
def estados_lote_list(request):
    ctx = _get_context_base(request)
    q = request.GET.get("q", "").strip()
    
    # Se usa 'codigo' para el ordenamiento
    items = EstadoLote.objects.all().order_by('codigo')
    
    if q:
        items = items.filter(Q(codigo__icontains=q) | Q(descripcion__icontains=q))
    
    ctx.update({
        "items": items,
        "q": q,
        "titulo": "Estados de Lote"
    })
    return render(request, "miapp/configuracion/estado_lote_list.html", ctx)

@login_required
@requiere_admin_negocio
def estado_lote_crear(request):
    return _procesar_estado_lote(request, pk=None)

@login_required
@requiere_admin_negocio
def estado_lote_editar(request, pk):
    return _procesar_estado_lote(request, pk=pk)

def _procesar_estado_lote(request, pk):
    ctx = _get_context_base(request)
    instance = get_object_or_404(EstadoLote, pk=pk) if pk else None
    modo = "Editar" if pk else "Crear"
    
    if request.method == "POST":
        form = EstadoLoteForm(request.POST, instance=instance)
        if form.is_valid():
            item = form.save()
            messages.success(request, f"Estado '{item.nombre}' guardado con éxito.")
            return redirect("miapp:estados_lote_gestion")
        else:
            messages.error(request, "Error en los datos del estado.")
    else:
        form = EstadoLoteForm(instance=instance, initial={'es_activo': True} if not pk else None)

    ctx.update({
        "form": form,
        "modo": modo,
        "titulo": f"{modo} Estado de Lote"
    })
    return render(request, "miapp/configuracion/estado_lote_form.html", ctx)

# ============================================================
# GESTIÓN DE ESTADOS DE PEDIDO
# ============================================================

@login_required
@requiere_admin_negocio
def estados_pedido_list(request):
    ctx = _get_context_base(request)
    q = request.GET.get("q", "").strip()
    
    # ELIMINADO: Se quitó 'etapa' del order_by ya que el campo no existe en el modelo
    items = EstadoPedido.objects.all().annotate(
        num_pedidos=Count('pedidos') 
    ).order_by('codigo') # Ordenamos solo por código
    
    if q:
        items = items.filter(Q(codigo__icontains=q) | Q(descripcion__icontains=q))
    
    ctx.update({
        "items": items,
        "q": q,
        "titulo": "Estados de Pedido"
    })
    return render(request, "miapp/configuracion/estado_pedido_list.html", ctx)

@login_required
@requiere_admin_negocio
def estado_pedido_crear(request):
    return _procesar_estado_pedido(request, pk=None)

@login_required
@requiere_admin_negocio
def estado_pedido_editar(request, pk):
    return _procesar_estado_pedido(request, pk=pk)

def _procesar_estado_pedido(request, pk):
    ctx = _get_context_base(request)
    instance = get_object_or_404(EstadoPedido, pk=pk) if pk else None
    modo = "Editar" if pk else "Crear"
    
    if request.method == "POST":
        form = EstadoPedidoForm(request.POST, instance=instance)
        if form.is_valid():
            nuevo_estado = form.cleaned_data.get('es_activo')
            if instance and instance.es_activo and not nuevo_estado:
                # CORRECCIÓN: Verifica si hay pedidos vinculados antes de desactivar
                if instance.pedidos.exists():
                    messages.error(request, "No se puede desactivar: Hay pedidos registrados con este estado.")
                    ctx.update({"form": form, "modo": modo, "titulo": f"{modo} Estado"})
                    return render(request, "miapp/configuracion/estado_pedido_form.html", ctx)

            item = form.save()
            messages.success(request, f"Estado '{item.codigo}' guardado correctamente.")
            return redirect("miapp:estados_pedido_gestion")
    else:
        form = EstadoPedidoForm(instance=instance, initial={'es_activo': True} if not pk else None)

    ctx.update({
        "form": form,
        "modo": modo,
        "titulo": f"{modo} Estado de Pedido"
    })
    return render(request, "miapp/configuracion/estado_pedido_form.html", ctx)

# ============================================================
# GESTIÓN DE TIPOS DE MOVIMIENTO
# ============================================================

@login_required
@requiere_admin_negocio
def tipos_movimiento_list(request):
    ctx = _get_context_base(request)
    q = request.GET.get("q", "").strip()
    
    items = TipoMovimiento.objects.all().order_by('codigo')
    if q:
        items = items.filter(Q(codigo__icontains=q) | Q(descripcion__icontains=q))
    
    ctx.update({
        "items": items,
        "q": q,
        "titulo": "Tipos de Movimiento"
    })
    return render(request, "miapp/configuracion/tipo_movimiento_list.html", ctx)

@login_required
@requiere_admin_negocio
def tipo_movimiento_crear(request):
    return _procesar_tipo_movimiento(request, pk=None)

@login_required
@requiere_admin_negocio
def tipo_movimiento_editar(request, pk):
    return _procesar_tipo_movimiento(request, pk=pk)

def _procesar_tipo_movimiento(request, pk):
    ctx = _get_context_base(request)
    instance = get_object_or_404(TipoMovimiento, pk=pk) if pk else None
    modo = "Editar" if pk else "Crear"
    
    if request.method == "POST":
        form = TipoMovimientoForm(request.POST, instance=instance)
        if form.is_valid():
            try:
                item = form.save()
                messages.success(request, f"Tipo de movimiento '{item.codigo}' guardado.")
                return redirect("miapp:tipos_movimiento_gestion")
            except ValidationError as e:
                messages.error(request, str(e))
        else:
            messages.error(request, "Corrija los errores en el formulario.")
    else:
        form = TipoMovimientoForm(instance=instance, initial={'es_activo': True} if not pk else None)

    ctx.update({
        "form": form,
        "modo": modo,
        "titulo": f"{modo} Tipo de Movimiento"
    })
    return render(request, "miapp/configuracion/tipo_movimiento_form.html", ctx)

# ============================================================
# GESTIÓN DE PAÍSES
# ============================================================

@login_required
@requiere_admin_negocio
def paises_list(request):
    ctx = _get_context_base(request)
    q = request.GET.get("q", "").strip()
    
    items = Pais.objects.all().order_by('nombre')
    if q:
        items = items.filter(Q(nombre__icontains=q) | Q(codigo_iso__icontains=q))
    
    ctx.update({
        "items": items,
        "q": q,
        "titulo": "Gestión de Países"
    })
    return render(request, "miapp/configuracion/pais_list.html", ctx)

@login_required
@requiere_admin_negocio
def pais_crear(request):
    return _procesar_pais(request, pk=None)

@login_required
@requiere_admin_negocio
def pais_editar(request, pk):
    return _procesar_pais(request, pk=pk)

def _procesar_pais(request, pk):
    ctx = _get_context_base(request)
    instance = get_object_or_404(Pais, pk=pk) if pk else None
    modo = "Editar" if pk else "Crear"
    
    if request.method == "POST":
        form = PaisForm(request.POST, instance=instance)
        if form.is_valid():
            # Validación de integridad: No desactivar si está en uso
            nuevo_estado = form.cleaned_data.get('es_activo')
            if instance and instance.es_activo and not nuevo_estado:
                # Revisamos relaciones (asumiendo related_name='proveedores' y 'clientes')
                if instance.proveedor_set.exists() or instance.cliente_set.exists():
                    messages.error(request, "No se puede desactivar: Este país ya está asignado a registros activos.")
                    ctx.update({"form": form, "modo": modo, "titulo": f"{modo} País"})
                    return render(request, "miapp/configuracion/pais_form.html", ctx)

            item = form.save()
            messages.success(request, f"País '{item.nombre}' guardado correctamente.")
            return redirect("miapp:paises_gestion")
    else:
        form = PaisForm(instance=instance, initial={'es_activo': True} if not pk else None)

    ctx.update({
        "form": form,
        "modo": modo,
        "titulo": f"{modo} País"
    })
    return render(request, "miapp/configuracion/pais_form.html", ctx)


