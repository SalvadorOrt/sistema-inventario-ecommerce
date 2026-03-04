# Django
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q, Max, Prefetch
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.cache import never_cache

# Helpers
from .helpers import requiere_admin_negocio, _get_context_base

# Local: modelos
from ..models import (
    Bodega,
    ZonaAlmacenamiento,
    TipoAlmacenamiento,
    Rack,
    UbicacionFisica,
    StockLote,PerfilUsuario
)

# Local: formularios
from ..forms.infraestructura_forms import (
    BodegaForm,
    ZonaAlmacenamientoForm,
    RackForm,
)


# ============================================================
# 1. BODEGAS
# ============================================================

@never_cache
@login_required
@requiere_admin_negocio
def bodegas_gestion(request):
    ctx = _get_context_base(request)
    q = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "")
    orden = request.GET.get("orden", "nombre")
    
    filtros = Q()
    if q:
        filtros &= (Q(nombre__icontains=q) | Q(direccion__icontains=q))
    if estado == "activo": filtros &= Q(es_activo=True)
    elif estado == "inactivo": filtros &= Q(es_activo=False)

    items = Bodega.objects.filter(filtros).annotate(num_zonas=Count('zonas')).order_by(orden)

    ctx.update({
        "titulo": "Gestión de Sedes y Bodegas",
        "items": items,
        "q": q,
        "estado_actual": estado,
        "orden_actual": orden,
        "total_resultados": items.count(),
    })
    return render(request, "miapp/infraestructura/bodegas_list.html", ctx)

@never_cache
@login_required
@requiere_admin_negocio
def bodega_detalle(request, pk):
    ctx = _get_context_base(request)
    bodega = get_object_or_404(Bodega, pk=pk)
    zonas = bodega.zonas.all().order_by('codigo')
    ctx.update({"bodega": bodega, "zonas": zonas, "titulo": f"Sede: {bodega.nombre}"})
    return render(request, "miapp/infraestructura/bodega_detail.html", ctx)

@login_required
@requiere_admin_negocio
def bodega_crear(request): return _procesar_bodega(request, pk=None)

@login_required
@requiere_admin_negocio
def bodega_editar(request, pk): return _procesar_bodega(request, pk=pk)

def _procesar_bodega(request, pk):
    ctx = _get_context_base(request)
    instance = get_object_or_404(Bodega, pk=pk) if pk else None
    modo = "Editar" if pk else "Crear"
    if request.method == "POST":
        form = BodegaForm(request.POST, instance=instance)
        if form.is_valid():
            bodega = form.save()
            messages.success(request, f"Bodega '{bodega.nombre}' guardada.")
            return redirect("miapp:bodegas_gestion")
    else:
        form = BodegaForm(instance=instance, initial={'es_activo': True} if not pk else None)
    ctx.update({"form": form, "modo": modo, "titulo": f"{modo} Bodega"})
    return render(request, "miapp/infraestructura/bodega_form.html", ctx)

# ============================================================
# 2. ZONAS
# ============================================================

@never_cache
@login_required
@requiere_admin_negocio
def zonas_gestion(request):
    ctx = _get_context_base(request)
    q = request.GET.get("q", "").strip()
    
    # --- FILTROS ---
    f_tipo = request.GET.get("f_tipo", "")
    f_estado = request.GET.get("f_estado", "")

    # 1. Preparar QuerySet de Zonas
    zonas_qs = ZonaAlmacenamiento.objects.select_related('tipo_almacenamiento')\
        .annotate(num_racks=Count('racks'))\
        .order_by('codigo')

    if q:
        zonas_qs = zonas_qs.filter(Q(nombre__icontains=q) | Q(codigo__icontains=q))
    
    if f_tipo:
        zonas_qs = zonas_qs.filter(tipo_almacenamiento_id=f_tipo)

    if f_estado == "activos":
        zonas_qs = zonas_qs.filter(es_activo=True)
    elif f_estado == "inactivos":
        zonas_qs = zonas_qs.filter(es_activo=False)

    # 2. Preparar Bodegas e inyectar zonas filtradas
    bodegas_list = Bodega.objects.filter(es_activo=True)\
        .prefetch_related(Prefetch('zonas', queryset=zonas_qs, to_attr='zonas_filtradas'))\
        .order_by('nombre')

    if q or f_tipo or f_estado:
        bodegas_list = [b for b in bodegas_list if len(b.zonas_filtradas) > 0]

    ctx.update({
        "titulo": "Maestro de Zonas",
        "bodegas_list": bodegas_list,
        "tipos_almacenamiento": TipoAlmacenamiento.objects.filter(es_activo=True),
        "q": q,
        "f_tipo": int(f_tipo) if f_tipo else "",
        "f_estado": f_estado
    })
    return render(request, "miapp/infraestructura/zonas_list.html", ctx)

# En miapp/views/infraestructura_views.py

@never_cache
@login_required
@requiere_admin_negocio
def zona_detalle(request, pk):
    ctx = _get_context_base(request)
    
    # 1. Obtener la Zona y sus Racks relacionados
    zona = get_object_or_404(ZonaAlmacenamiento.objects.select_related('bodega'), pk=pk)
    racks = zona.racks.all().annotate(num_ubicaciones=Count('ubicaciones')).order_by('codigo')
    
    # 2. Capturar URL de retorno (Clave para la navegación fluida desde el Mapa)
    # Si vienes del mapa, 'next' contendrá algo como: /infraestructura/mapa/?bodega=1&zona=5
    url_retorno = request.GET.get('next')

    ctx.update({
        "zona": zona, 
        "racks": racks, 
        "titulo": f"Zona: {zona.nombre}",
        "url_retorno": url_retorno  # Pasamos esto al HTML para el botón "Volver"
    })
    return render(request, "miapp/infraestructura/zona_detail.html", ctx)

@login_required
@requiere_admin_negocio
def zona_crear(request): return _procesar_zona(request, pk=None)

@login_required
@requiere_admin_negocio
def zona_editar(request, pk): return _procesar_zona(request, pk=pk)

def _procesar_zona(request, pk):
    ctx = _get_context_base(request)
    instance = get_object_or_404(ZonaAlmacenamiento, pk=pk) if pk else None
    modo = "Editar" if pk else "Crear"
    
    # 1. Capturamos bodega de la URL
    bodega_id = request.GET.get('bodega')

    if request.method == "POST":
        data = request.POST.copy()
        if bodega_id and not pk:
            data['bodega'] = bodega_id
            
        form = ZonaAlmacenamientoForm(data, instance=instance)
        
        if form.is_valid():
            # VALIDACIÓN DE SEGURIDAD (Si hay stock, no cambiar tipo)
            if instance:
                nuevo_tipo = form.cleaned_data['tipo_almacenamiento']
                if instance.tipo_almacenamiento != nuevo_tipo:
                    hay_stock_real = StockLote.objects.filter(
                        ubicacion__rack__zona=instance,
                        cantidad_disponible__gt=0
                    ).exists()
                    
                    if hay_stock_real:
                        messages.error(request, f"ACCIÓN DENEGADA: Hay stock físico en esta zona. Vacíe la zona antes de cambiar su tipo.")
                        ctx.update({"form": form, "modo": modo, "titulo": f"{modo} Zona", "zona": instance})
                        return render(request, "miapp/infraestructura/zona_form.html", ctx)
            
            zona = form.save()
            messages.success(request, f"Zona '{zona.codigo}' configurada correctamente.")
            return redirect("miapp:bodega_detalle", pk=zona.bodega.id)
    else:
        initial = {}
        if bodega_id:
            bodega_obj = get_object_or_404(Bodega, id=bodega_id)
            initial['bodega'] = bodega_id
            initial['bodega_nombre'] = bodega_obj.nombre 
        
        form = ZonaAlmacenamientoForm(instance=instance, initial=initial)

    # Inyección de nombre para visualización
    if bodega_id and not request.GET.get('bodega_nombre'):
        try:
            b_nombre = Bodega.objects.get(id=bodega_id).nombre
            mutable_get = request.GET.copy()
            mutable_get['bodega_nombre'] = b_nombre
            request.GET = mutable_get
        except Bodega.DoesNotExist:
            pass

    ctx.update({
        "form": form, 
        "modo": modo, 
        "titulo": f"{modo} Zona",
        "zona": instance 
    })
    return render(request, "miapp/infraestructura/zona_form.html", ctx)

# ============================================================
# 3. RACKS
# ============================================================

# miapp/views/infraestructura_views.py

@never_cache
@login_required
@requiere_admin_negocio
def racks_gestion(request):
    ctx = _get_context_base(request)
    
    # --- 1. CAPTURA DE PARÁMETROS ---
    q = request.GET.get("q", "").strip()
    f_bodega = request.GET.get("f_bodega", "")
    f_zona = request.GET.get("f_zona", "")
    f_estado = request.GET.get("f_estado", "") # 'activo', 'inactivo', o ''

    # --- 2. FILTROS BASE PARA RACKS ---
    # Filtramos los racks primero para no traer datos innecesarios
    filtros_rack = Q()
    
    if q:
        filtros_rack &= (
            Q(codigo__icontains=q) | 
            Q(descripcion__icontains=q) |
            Q(zona__nombre__icontains=q)
        )
    
    if f_zona:
        filtros_rack &= Q(zona_id=f_zona)
        
    if f_estado == 'activo':
        filtros_rack &= Q(es_activo=True)
    elif f_estado == 'inactivo':
        filtros_rack &= Q(es_activo=False)

    # --- 3. FILTRADO DE JERARQUÍA (BODEGAS) ---
    # Si seleccionaron bodega, filtramos la lista raíz
    bodegas_qs = Bodega.objects.filter(es_activo=True).order_by('nombre')
    if f_bodega:
        bodegas_qs = bodegas_qs.filter(id=f_bodega)

    # --- 4. CONSTRUCCIÓN DE LA ESTRUCTURA ---
    estructura_datos = []

    for bodega in bodegas_qs:
        # Buscamos zonas de esta bodega
        zonas_qs = ZonaAlmacenamiento.objects.filter(bodega=bodega, es_activo=True).order_by('codigo')
        
        # Si hay filtro de zona, aplicarlo aquí también para optimizar
        if f_zona:
            zonas_qs = zonas_qs.filter(id=f_zona)

        zonas_con_racks = []

        for zona in zonas_qs:
            # Buscamos los racks filtrados que pertenecen a esta zona
            racks = Rack.objects.filter(zona=zona).filter(filtros_rack).annotate(
                num_niveles=Count('ubicaciones')
            ).order_by('codigo')

            if racks.exists():
                zonas_con_racks.append({
                    'info': zona,
                    'racks': racks
                })
        
        # Solo añadimos la bodega si tiene zonas con racks que coincidan
        if zonas_con_racks:
            estructura_datos.append({
                'bodega': bodega,
                'zonas': zonas_con_racks
            })

    ctx.update({
        "titulo": "Gestión de Racks",
        "estructura_datos": estructura_datos,
        # Listas para llenar los selects
        "bodegas_filtro": Bodega.objects.filter(es_activo=True),
        "zonas_filtro": ZonaAlmacenamiento.objects.filter(es_activo=True).select_related('bodega'),
        # Mantener estado de filtros en el HTML
        "q": q,
        "f_bodega": int(f_bodega) if f_bodega else "",
        "f_zona": int(f_zona) if f_zona else "",
        "f_estado": f_estado
    })
    return render(request, "miapp/infraestructura/racks_list.html", ctx)

@never_cache
@login_required
@requiere_admin_negocio
def rack_detalle(request, pk):
    ctx = _get_context_base(request)
    # Optimizamos la consulta trayendo también el tipo de almacenamiento para evitar N+1 queries
    rack = get_object_or_404(Rack.objects.select_related('zona__bodega', 'zona__tipo_almacenamiento'), pk=pk)
    
    niveles = rack.ubicaciones.prefetch_related(
        Prefetch(
            'lotes', 
            queryset=StockLote.objects.filter(cantidad_disponible__gt=0).select_related('producto'),
            to_attr='stock_activo'
        )
    ).order_by('-nivel_fila')

    # --- NUEVO: Capturar URL de retorno ---
    # Esto captura ?next=... de la URL para que el botón "Volver" sepa a dónde ir
    url_retorno = request.GET.get('next')

    ctx.update({
        "rack": rack, 
        "niveles": niveles, 
        "titulo": f"Rack {rack.codigo}",
        "url_retorno": url_retorno # Enviamos al template
    })
    return render(request, "miapp/infraestructura/rack_detail.html", ctx)

@login_required
@requiere_admin_negocio
def rack_crear(request): return _procesar_rack(request, pk=None)

@login_required
@requiere_admin_negocio
def rack_editar(request, pk): return _procesar_rack(request, pk=pk)

def _procesar_rack(request, pk):
    ctx = _get_context_base(request)
    instance = get_object_or_404(Rack, pk=pk) if pk else None
    modo = "Editar" if pk else "Crear"
    
    zona_id = request.GET.get('zona')
    
    # --- CORRECCIÓN AQUÍ ---
    # Buscamos 'next' en GET (url) O en POST (formulario hidden input)
    # Esto asegura que al dar click en Guardar, el sistema no olvide de dónde venías.
    url_retorno = request.GET.get('next') or request.POST.get('next')

    if request.method == "POST":
        data = request.POST.copy()
        if zona_id and not pk:
            data['zona'] = zona_id
            
        form = RackForm(data, instance=instance)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    rack = form.save()
                    if not pk:
                        cant = form.cleaned_data.get('cantidad_niveles', 1)
                        for i in range(1, cant + 1):
                            UbicacionFisica.objects.create(rack=rack, nivel_fila=i)
                
                messages.success(request, f"Rack '{rack.codigo}' guardado correctamente.")
                
                # Al guardar, si tenemos retorno capturado, volvemos ahí
                if url_retorno:
                    return redirect(url_retorno)
                
                # Si no, comportamiento default (ir al detalle de zona)
                return redirect("miapp:zona_detalle", pk=rack.zona.id)
                
            except Exception as e:
                messages.error(request, f"Error: {e}")
    else:
        initial = {}
        if zona_id:
            initial['zona'] = zona_id
        form = RackForm(instance=instance, initial=initial)

    # Lógica para Breadcrumbs
    zona_obj = None
    if zona_id:
        zona_obj = ZonaAlmacenamiento.objects.filter(id=zona_id).first()
    elif instance:
        zona_obj = instance.zona

    ctx.update({
        "form": form, 
        "modo": modo, 
        "titulo": f"{modo} Rack",
        "zona_padre": zona_obj,
        "url_retorno": url_retorno # Enviamos al template para ponerlo en el input hidden
    })
    return render(request, "miapp/infraestructura/rack_form.html", ctx)
# ============================================================
# 4. ACCIONES DINÁMICAS Y MAPA
# ============================================================

@login_required
def nivel_añadir(request, rack_id):
    rack = get_object_or_404(Rack, pk=rack_id)
    
    # Lógica de negocio (Crear nivel)
    ultimo = rack.ubicaciones.order_by('-nivel_fila').first()
    siguiente = (ultimo.nivel_fila + 1) if ultimo else 1
    UbicacionFisica.objects.create(rack=rack, nivel_fila=siguiente)
    
    # --- CORRECCIÓN: Mantener el rastro ---
    # Capturamos el 'next' que viene en la URL al hacer clic en "Añadir Nivel"
    url_retorno = request.GET.get('next')
    
    # Construimos la redirección hacia el detalle
    redirect_url = f"{redirect('miapp:rack_detalle', pk=rack_id).url}"
    
    # Si tenemos retorno, se lo volvemos a pegar a la URL de destino
    if url_retorno:
        from urllib.parse import quote
        redirect_url += f"?next={quote(url_retorno)}"
        
    return redirect(redirect_url)

@login_required
def nivel_eliminar(request, pk):
    ubicacion = get_object_or_404(UbicacionFisica, pk=pk)
    rid = ubicacion.rack.id
    
    # Lógica de negocio (Eliminar)
    if ubicacion.esta_libre():
        ubicacion.delete()
        messages.success(request, "Nivel eliminado.")
    else:
        messages.error(request, "No se puede eliminar: tiene stock.")
        
    # --- CORRECCIÓN: Mantener el rastro ---
    url_retorno = request.GET.get('next')
    
    redirect_url = f"{redirect('miapp:rack_detalle', pk=rid).url}"
    
    if url_retorno:
        from urllib.parse import quote
        redirect_url += f"?next={quote(url_retorno)}"
        
    return redirect(redirect_url)

# miapp/views/infraestructura_views.py
















@never_cache
@login_required
# Eliminamos @requiere_admin_negocio para permitir la entrada al bodeguero
def mapa_distribucion(request):
    ctx = _get_context_base(request)
    perfil = getattr(request.user, 'perfil', None)
    
    # 1. Identificar Rol y Restricción de Bodega
    es_admin = request.user.is_superuser or (perfil and perfil.rol_negocio == PerfilUsuario.RolNegocio.ADMIN_SISTEMA)
    mi_bodega = perfil.bodega if perfil else None

    # Capturamos parámetros de la URL
    bodega_id = request.GET.get("bodega")
    zona_id = request.GET.get("zona")
    
    bodega_seleccionada = None
    zona_seleccionada = None
    matriz = []
    racks = []
    zonas_disponibles = []

    # 2. SEGURIDAD DE ACCESO: Forzar la bodega del bodeguero
    if not es_admin:
        if not mi_bodega:
            messages.error(request, "No tienes una bodega física asignada para ver el mapa.")
            return redirect('miapp:inicio')
        # El bodeguero solo puede ver SU bodega, ignoramos lo que venga por URL
        bodega_seleccionada = mi_bodega
    else:
        # El admin puede elegir de la URL o del selector
        if bodega_id:
            bodega_seleccionada = get_object_or_404(Bodega, id=bodega_id)

    # 3. Cargar Zonas de la bodega validada
    if bodega_seleccionada:
        zonas_disponibles = bodega_seleccionada.zonas.filter(es_activo=True).order_by('codigo')

    # 4. Generar Mapa si hay una zona seleccionada
    if zona_id and bodega_seleccionada:
        # Validamos que la zona pertenezca a la bodega permitida
        zona_seleccionada = zonas_disponibles.filter(id=zona_id).first()
        
        if zona_seleccionada:
            racks = zona_seleccionada.racks.all().order_by('codigo').prefetch_related(
                Prefetch('ubicaciones', queryset=UbicacionFisica.objects.select_related('rack').prefetch_related(
                    Prefetch('lotes', queryset=StockLote.objects.filter(cantidad_disponible__gt=0), to_attr='lotes_activos')
                ))
            )
            
            max_n = UbicacionFisica.objects.filter(rack__zona=zona_seleccionada).aggregate(Max('nivel_fila'))['nivel_fila__max'] or 0
            
            for n in range(max_n, 0, -1):
                celdas = []
                for r in racks:
                    ubi = next((u for u in r.ubicaciones.all() if u.nivel_fila == n), None)
                    celdas.append(ubi)
                matriz.append({'nivel': n, 'celdas': celdas})

    ctx.update({
        "titulo": "Mapa de Distribución 2D",
        # El selector de bodegas solo muestra todas al admin; al bodeguero solo la suya
        "bodegas": Bodega.objects.filter(es_activo=True) if es_admin else [mi_bodega],
        "bodega_seleccionada": bodega_seleccionada,
        "zonas_disponibles": zonas_disponibles,
        "zona_seleccionada": zona_seleccionada,
        "matriz": matriz,
        "racks_header": racks,
        "es_admin": es_admin,
    })
    return render(request, "miapp/infraestructura/mapa_distribucion.html", ctx)














