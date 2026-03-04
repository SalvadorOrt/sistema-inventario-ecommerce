from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, F
from datetime import date, timedelta # <--- Necesario para calcular alertas de vencimiento

# Importamos TODOS los modelos necesarios (Agregamos Marca y Proveedor)
from ..models import StockLote, Bodega, EstadoLote, Categoria, Marca, Proveedor
from .helpers import _get_context_base
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from ..models import StockLote, EstadoLote # Asegúrate de importar EstadoLote
from .helpers import _get_context_base
@login_required
def inventario_global_list(request):
    """
    Vista principal del monitor de inventario con filtros avanzados.
    """
    ctx = _get_context_base(request)
    
    # --- 1. CAPTURA DE PARÁMETROS ---
    q = request.GET.get("q", "").strip()
    f_bodega = request.GET.get("f_bodega", "")
    f_estado = request.GET.get("f_estado", "")
    f_cat = request.GET.get("f_cat", "")
    orden = request.GET.get("orden", "reciente")
    
    # Parametros Avanzados
    f_marca = request.GET.get("f_marca", "")
    f_proveedor = request.GET.get("f_proveedor", "")
    f_alerta = request.GET.get("f_alerta", "")

    # --- 2. QUERY BASE OPTIMIZADA ---
    items = StockLote.objects.select_related(
        'producto', 
        'producto__categoria', 
        'producto__marca',
        'ubicacion__rack__zona__bodega', 
        'estado_lote',
        'proveedor' 
    ).filter(cantidad_disponible__gt=0)

    # --- 3. APLICACIÓN DE FILTROS ---
    
    # Búsqueda General
    if q:
        items = items.filter(
            Q(producto__nombre__icontains=q) | 
            Q(producto__codigo_sku__icontains=q) |
            Q(lote__icontains=q) |
            Q(ubicacion__codigo_celda__icontains=q)
        )
    
    # Filtros Estándar
    if f_bodega and f_bodega.isdigit():
        items = items.filter(ubicacion__rack__zona__bodega_id=int(f_bodega))
        
    if f_estado and f_estado.isdigit():
        items = items.filter(estado_lote_id=int(f_estado))

    if f_cat and f_cat.isdigit():
        items = items.filter(producto__categoria_id=int(f_cat))
        
    # Filtros Avanzados
    if f_marca and f_marca.isdigit():
        items = items.filter(producto__marca_id=int(f_marca))
        
    if f_proveedor and f_proveedor.isdigit():
        items = items.filter(proveedor_id=int(f_proveedor))

    # Lógica de Alertas (Fechas)
    hoy = date.today()
    if f_alerta == 'vencidos':
        items = items.filter(fecha_caducidad__lt=hoy)
    elif f_alerta == 'por_vencer_30':
        limite = hoy + timedelta(days=30)
        items = items.filter(fecha_caducidad__range=[hoy, limite])
    elif f_alerta == 'por_vencer_60':
        limite = hoy + timedelta(days=60)
        items = items.filter(fecha_caducidad__range=[hoy, limite])

    # --- 4. ORDENAMIENTO INTELIGENTE ---
    if orden == 'reciente':
        # Ordenar por llegada, y desempate por nombre
        items = items.order_by('-fecha_entrada', 'producto__nombre')
        
    elif orden == 'nombre':
        # Alfabético estricto
        items = items.order_by('producto__nombre', 'fecha_caducidad')
        
    elif orden == 'fefo':
        # CORRECCIÓN CLAVE: 
        # 1. Filtramos para que SOLO salgan los que tienen fecha (excluye FIFO)
        # 2. Ordenamos por fecha y luego por nombre del producto
        items = items.filter(fecha_caducidad__isnull=False).order_by('fecha_caducidad', 'producto__nombre')
        
    elif orden == 'ubicacion':
        items = items.order_by('ubicacion__codigo_celda', 'producto__nombre')

    # --- 5. PAGINACIÓN ---
    paginator = Paginator(items, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    filtros_avanzados = any([f_marca, f_proveedor, f_alerta])

    # --- 6. CONTEXTO ---
    ctx.update({
        "items": page_obj,
        "bodegas": Bodega.objects.filter(es_activo=True),
        "estados": EstadoLote.objects.filter(es_activo=True),
        "categorias": Categoria.objects.filter(es_activo=True),
        "marcas": Marca.objects.filter(es_activo=True),
        "proveedores": Proveedor.objects.filter(es_activo=True),
        
        "filtros": {
            "q": q,
            "f_bodega": int(f_bodega) if f_bodega.isdigit() else "",
            "f_estado": int(f_estado) if f_estado.isdigit() else "",
            "f_cat": int(f_cat) if f_cat.isdigit() else "",
            "f_marca": int(f_marca) if f_marca.isdigit() else "",
            "f_proveedor": int(f_proveedor) if f_proveedor.isdigit() else "",
            "f_alerta": f_alerta,
            "orden": orden
        },
        "filtros_avanzados": filtros_avanzados,
        "titulo": "Monitor de Existencias",
        "hoy": hoy
    })
    
    return render(request, "miapp/gestion/inventario_list.html", ctx)

# --- Función auxiliar de seguridad ---
def es_admin(user):
    return user.is_staff or user.is_superuser

# --- Detalle del Lote (Versión Correcta) ---
@login_required
def lote_detail(request, pk):
    """
    Vista de detalle de un lote específico y su trazabilidad.
    Incluye la lista de estados para el modal de edición.
    """
    # 1. Traemos el lote
    lote = get_object_or_404(
        StockLote.objects.select_related(
            'producto', 
            'ubicacion__rack__zona__bodega', 
            'estado_lote', 
            'proveedor'
        ), 
        pk=pk
    )
    
    # 2. Historial de movimientos
    movimientos = lote.movimientos.select_related('tipo_movimiento', 'usuario').all().order_by('-fecha', '-id')

    # 3. Contexto
    ctx = _get_context_base(request)
    ctx.update({
        'lote': lote,
        'movimientos': movimientos,
        'titulo': f'Trazabilidad: {lote.lote}',
        # ESTO ES VITAL PARA EL MODAL:
        'estados_posibles': EstadoLote.objects.filter(es_activo=True)
    })
    return render(request, "miapp/gestion/lote_detail.html", ctx)

# --- Acción de Cambiar Estado ---
@login_required
@user_passes_test(es_admin) # Solo staff puede ejecutar esto
def lote_cambiar_estado(request, pk):
    if request.method == 'POST':
        lote = get_object_or_404(StockLote, pk=pk)
        nuevo_estado_id = request.POST.get('nuevo_estado')
        motivo = request.POST.get('motivo', 'Cambio manual por administrador')
        
        if nuevo_estado_id:
            antiguo_estado = lote.estado_lote.codigo
            lote.estado_lote_id = nuevo_estado_id
            lote.save()
            
            # Mensaje de confirmación visual
            messages.success(request, f"Lote actualizado correctamente: {antiguo_estado} -> Nuevo Estado")
            
    return redirect('miapp:lote_detail', pk=pk)