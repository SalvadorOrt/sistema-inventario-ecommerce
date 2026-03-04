from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.contrib import messages
from django.db import transaction

from django.db.models import Q, Sum, Count, F, Value, DecimalField, Prefetch, Avg, Max
from django.db.models.functions import Coalesce

from ..models import (
    Producto, ImagenProducto, Categoria, Marca, Proveedor, Pais,
    TipoAlmacenamiento, ClaseProducto, Impuesto,
    InventarioProducto, StockLote, DetallePedido,
    Cliente, TipoCliente, EstadoPedido,Compra
)
from ..forms.catalogo_forms import (
    ProductoForm, ImagenProductoFormSet,
    CategoriaForm, MarcaForm, ProveedorForm,
    ClienteForm,
)

# Importación consolidada de helpers y decoradores
from .helpers import (
    requiere_admin_negocio, 
    _get_context_base, 
    requiere_ventas_o_admin, 
    requiere_bodega_o_admin
)

# ============================================================
# 1. GESTIÓN DE PRODUCTOS
# ============================================================

@never_cache
@login_required
@requiere_bodega_o_admin
def productos_gestion(request):
    """Listado principal de productos con filtros avanzados."""
    ctx = _get_context_base(request)
    
    # Captura de parámetros
    q = request.GET.get("q", "").strip()
    f_cat = request.GET.get("f_cat", "")
    f_marca = request.GET.get("f_marca", "")
    f_estado = request.GET.get("f_estado", "")
    f_tipo_alm = request.GET.get("f_tipo_alm", "")
    f_estrategia = request.GET.get("f_estrategia", "")
    f_clase = request.GET.get("f_clase", "")
    f_impuesto = request.GET.get("f_impuesto", "")
    f_precio_min = request.GET.get("p_min", "")
    f_precio_max = request.GET.get("p_max", "")
    
    # Construcción de filtros
    filtros = Q()
    if q: filtros &= (Q(nombre__icontains=q) | Q(codigo_sku__icontains=q) | Q(codigo_barras__icontains=q))
    if f_cat: filtros &= Q(categoria_id=f_cat)
    if f_marca: filtros &= Q(marca_id=f_marca)
    if f_tipo_alm: filtros &= Q(tipo_almacenamiento_id=f_tipo_alm)
    if f_estrategia: filtros &= Q(estrategia_salida=f_estrategia)
    if f_clase: filtros &= Q(clase_producto_id=f_clase)
    if f_impuesto: filtros &= Q(impuesto_id=f_impuesto)

    if f_estado == 'activos': filtros &= Q(es_activo=True)
    elif f_estado == 'inactivos': filtros &= Q(es_activo=False)

    if f_precio_min:
        try: filtros &= Q(precio_venta__gte=float(f_precio_min))
        except ValueError: pass
    if f_precio_max:
        try: filtros &= Q(precio_venta__lte=float(f_precio_max))
        except ValueError: pass

    # Consulta principal
    productos = (
        Producto.objects.filter(filtros)
        .select_related("categoria", "marca", "tipo_almacenamiento", "clase_producto", "impuesto")
        .prefetch_related(
            Prefetch("imagenes", queryset=ImagenProducto.objects.filter(es_principal=True), to_attr="img_principal")
        )
        .order_by("-fecha_actualizacion")
    )

    items = []
    for p in productos:
        img = p.img_principal[0].imagen.url if p.img_principal else None
        items.append({"obj": p, "imagen": img})

    # Datos para filtros dependientes
    qs_cats = Categoria.objects.filter(es_activo=True).order_by('nombre')
    qs_marcas = Marca.objects.filter(es_activo=True).order_by('nombre')

    if f_marca: qs_cats = qs_cats.filter(productos__marca_id=f_marca).distinct()
    if f_cat: qs_marcas = qs_marcas.filter(productos__categoria_id=f_cat).distinct()

    ctx.update({
        "titulo": "Gestión de Productos",
        "items": items,
        "cats": qs_cats,
        "marcas": qs_marcas,
        "tipos_alm": TipoAlmacenamiento.objects.filter(es_activo=True).order_by('codigo'),
        "clases": ClaseProducto.objects.filter(es_activo=True).order_by('descripcion'), 
        "impuestos": Impuesto.objects.filter(es_activo=True).order_by('id'), 
        "estrategias": Producto.EstrategiaSalida.choices,
        "filtros": {
            "q": q, "f_cat": f_cat, "f_marca": f_marca,
            "f_estado": f_estado, "f_tipo_alm": f_tipo_alm,
            "f_estrategia": f_estrategia, "f_clase": f_clase, "f_impuesto": f_impuesto,
            "p_min": f_precio_min, "p_max": f_precio_max
        }
    })
    return render(request, "miapp/gestion/productos_list.html", ctx)


@never_cache
@login_required
@requiere_bodega_o_admin
def producto_crear(request):
    """Vista pública para crear producto."""
    return _procesar_formulario_producto(request, pk=None)


@never_cache
@login_required
@requiere_bodega_o_admin
def producto_editar(request, pk):
    """Vista pública para editar producto."""
    return _procesar_formulario_producto(request, pk=pk)


@never_cache
@login_required
@requiere_bodega_o_admin
def producto_detalle(request, id):
    """Vista de detalle de producto con imágenes."""
    ctx = _get_context_base(request)
    producto = get_object_or_404(Producto, pk=id)
    
    imagenes = ImagenProducto.objects.filter(producto=producto).order_by('orden')
    
    ctx.update({
        'producto': producto,
        'imagenes': imagenes,
        'titulo': f'Detalle: {producto.nombre}'
    })
    return render(request, 'miapp/gestion/producto_detail.html', ctx)


def _procesar_formulario_producto(request, pk=None):
    """Lógica interna unificada para Crear/Editar productos."""
    ctx = _get_context_base(request)
    
    if pk:
        instance = get_object_or_404(Producto, pk=pk)
        modo = "Editar"
    else:
        instance = None
        modo = "Crear"

    if request.method == "POST":
        form = ProductoForm(request.POST, request.FILES, instance=instance)
        formset = ImagenProductoFormSet(request.POST, request.FILES, instance=instance)

        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    producto = form.save()
                    formset.instance = producto
                    formset.save()
                
                messages.success(request, f"Producto '{producto.nombre}' guardado correctamente.")
                return redirect("miapp:productos_gestion")
                
            except Exception as e:
                messages.error(request, f"Error crítico al guardar: {e}")
        else:
            messages.error(request, "Error en el formulario. Revise los campos.")
    else:
        initial_data = {"es_activo": True} if not pk else None
        form = ProductoForm(instance=instance, initial=initial_data)
        formset = ImagenProductoFormSet(instance=instance)

    # Datos adicionales para la vista de edición (Inventario y Lotes)
    inventarios = []
    lotes = []
    stock_total = 0

    if instance:
        inventarios = (
            InventarioProducto.objects
            .filter(producto=instance, stock_actual__gt=0)
            .select_related('bodega')
            .order_by('-stock_actual')
        )
        stock_total = inventarios.aggregate(t=Sum('stock_actual'))['t'] or 0

        lotes = (
            StockLote.objects
            .filter(producto=instance, cantidad_disponible__gt=0)
            .select_related('ubicacion__rack__zona__bodega')
            .order_by('fecha_caducidad', 'fecha_entrada')
        )

    ctx.update({
        "titulo": f"{modo} Producto",
        "form": form,
        "formset": formset,
        "editando": pk is not None,
        "producto": instance,
        "inventarios": inventarios,
        "lotes": lotes,
        "stock_total": stock_total,
    })
    
    return render(request, "miapp/gestion/producto_form.html", ctx)


# ============================================================
# 2. GESTIÓN DE CATEGORÍAS
# ============================================================

@never_cache
@login_required
@requiere_bodega_o_admin
def categorias_gestion(request):
    """Listado estable de categorías."""
    ctx = _get_context_base(request)
    
    q = request.GET.get("q", "").strip()
    f_estado = request.GET.get("f_estado", "")
    
    filtros = Q()
    if q:
        filtros &= (Q(nombre__icontains=q) | Q(prefijo_sku__icontains=q))
    
    if f_estado == 'activos':
        filtros &= Q(es_activo=True)
    elif f_estado == 'inactivos':
        filtros &= Q(es_activo=False)

    items = (
        Categoria.objects.filter(filtros)
        .annotate(total_productos=Count('productos')) 
        .order_by('nombre')
    )

    ctx.update({
        "titulo": "Gestión de Categorías",
        "items": items,
        "filtros": {"q": q, "f_estado": f_estado}
    })
    return render(request, "miapp/gestion/categorias_list.html", ctx)

@never_cache
@login_required
@requiere_bodega_o_admin
def categoria_detalle(request, pk):
    """Vista de detalle de una categoría específica y sus productos."""
    ctx = _get_context_base(request)
    cat = get_object_or_404(Categoria, pk=pk)
    
    productos = (
        Producto.objects.filter(categoria=cat)
        .select_related("marca", "tipo_almacenamiento")
        .annotate(
            total_stock=Coalesce(Sum('inventarios__stock_actual'), 0)
        )
        .order_by('nombre')
    )
    
    ctx.update({
        "categoria": cat,
        "productos": productos,
        "titulo": f"Categoría: {cat.nombre}"
    })
    return render(request, "miapp/gestion/categoria_detail.html", ctx)


@never_cache
@login_required
@requiere_bodega_o_admin
def categoria_crear(request):
    """Vista pública para crear categoría."""
    return _procesar_categoria(request, pk=None)


@never_cache
@login_required
@requiere_bodega_o_admin # CORREGIDO: Bodega puede editar si hay error al crear
def categoria_editar(request, pk):
    """Vista pública para editar categoría."""
    return _procesar_categoria(request, pk=pk)


def _procesar_categoria(request, pk):
    """Lógica interna unificada para Crear/Editar categorías."""
    ctx = _get_context_base(request)
    instance = get_object_or_404(Categoria, pk=pk) if pk else None
    modo = "Editar" if pk else "Crear"

    if request.method == "POST":
        form = CategoriaForm(request.POST, instance=instance)
        if form.is_valid():
            cat = form.save()
            messages.success(request, f"Categoría '{cat.nombre}' guardada.")
            return redirect("miapp:categorias_gestion")
        else:
            messages.error(request, "Error en el formulario.")
    else:
        form = CategoriaForm(instance=instance, initial={'es_activo': True} if not pk else None)

    ctx.update({
        "titulo": f"{modo} Categoría",
        "form": form,
        "modo": modo
    })
    return render(request, "miapp/gestion/categoria_form.html", ctx)


# ============================================================
# GESTIÓN DE MARCAS
# ============================================================

@never_cache
@login_required
@requiere_bodega_o_admin
def marcas_gestion(request):
    ctx = _get_context_base(request)
    
    q = request.GET.get("q", "").strip()
    f_estado = request.GET.get("f_estado", "")
    f_uso = request.GET.get("f_uso", "")       
    f_cat = request.GET.get("f_cat", "")       
    
    filtros = Q()
    if q:
        filtros &= Q(nombre__icontains=q)
    
    if f_estado == 'activos':
        filtros &= Q(es_activo=True)
    elif f_estado == 'inactivos':
        filtros &= Q(es_activo=False)

    if f_cat:
        filtros &= Q(productos__categoria_id=f_cat)

    items = (
        Marca.objects.filter(filtros)
        .annotate(total_productos=Count('productos'))
        .order_by('nombre')
        .distinct()
    )

    if f_uso == 'con_productos':
        items = items.filter(total_productos__gt=0)
    elif f_uso == 'sin_productos':
        items = items.filter(total_productos=0)

    categorias = Categoria.objects.filter(es_activo=True).order_by('nombre')

    ctx.update({
        "titulo": "Gestión de Marcas",
        "items": items,
        "categorias": categorias, 
        "filtros": {
            "q": q, 
            "f_estado": f_estado, 
            "f_uso": f_uso,
            "f_cat": f_cat
        }
    })
    return render(request, "miapp/gestion/marcas_list.html", ctx)

@never_cache
@login_required
@requiere_bodega_o_admin
def marca_detalle(request, pk):
    ctx = _get_context_base(request)
    marca = get_object_or_404(Marca, pk=pk)
    
    productos = (
        Producto.objects.filter(marca=marca)
        .select_related("categoria", "tipo_almacenamiento")
        .annotate(
            total_stock=Coalesce(Sum('inventarios__stock_actual'), 0)
        )
        .order_by('nombre')
    )

    ctx.update({
        "marca": marca,
        "productos": productos,
        "titulo": f"Marca: {marca.nombre}"
    })
    return render(request, "miapp/gestion/marca_detail.html", ctx)

@never_cache
@login_required
@requiere_bodega_o_admin
def marca_crear(request):
    return _procesar_marca(request, pk=None)

@never_cache
@login_required
@requiere_bodega_o_admin
def marca_editar(request, pk):
    return _procesar_marca(request, pk=pk)

def _procesar_marca(request, pk):
    """Helper para crear/editar marcas."""
    ctx = _get_context_base(request)
    instance = get_object_or_404(Marca, pk=pk) if pk else None
    modo = "Editar" if pk else "Crear"

    if request.method == "POST":
        form = MarcaForm(request.POST, instance=instance)
        if form.is_valid():
            marca = form.save()
            messages.success(request, f"Marca '{marca.nombre}' guardada correctamente.")
            return redirect("miapp:marcas_gestion")
        else:
            messages.error(request, "Error en el formulario. Verifique los datos.")
    else:
        form = MarcaForm(instance=instance, initial={'es_activo': True} if not pk else None)

    ctx.update({
        "titulo": f"{modo} Marca",
        "form": form,
        "modo": modo
    })
    return render(request, "miapp/gestion/marca_form.html", ctx)


# ============================================================
# GESTIÓN DE PROVEEDORES
# ============================================================

@never_cache
@login_required
@requiere_bodega_o_admin
def proveedores_gestion(request):
    ctx = _get_context_base(request)
    
    # 1. Filtros
    q = request.GET.get("q", "").strip()
    f_pais = request.GET.get("f_pais", "")
    f_estado = request.GET.get("f_estado", "")
    
    filtros = Q()
    if q:
        filtros &= (Q(nombre__icontains=q) | Q(numero_identificacion__icontains=q))
    
    if f_pais:
        filtros &= Q(pais_id=f_pais)

    if f_estado == 'activos':
        filtros &= Q(es_activo=True)
    elif f_estado == 'inactivos':
        filtros &= Q(es_activo=False)

    # 2. Consulta (Optimizada con select_related)
    items = (
        Proveedor.objects.filter(filtros)
        .select_related('pais', 'tipo_identificacion')
        .order_by('nombre')
    )

    # 3. Contexto para selects
    paises = Pais.objects.filter(es_activo=True).order_by('nombre')

    ctx.update({
        "titulo": "Gestión de Proveedores",
        "items": items,
        "paises": paises,
        "filtros": {"q": q, "f_pais": f_pais, "f_estado": f_estado}
    })
    return render(request, "miapp/gestion/proveedores_list.html", ctx)

@never_cache
@login_required
@requiere_bodega_o_admin
def proveedor_detalle(request, pk):
    ctx = _get_context_base(request)
    proveedor = get_object_or_404(Proveedor, pk=pk)
    
    # 1. Obtener el historial de Compras
    # Usamos prefetch_related('detalles') para traer los productos de una sola vez
    compras = (
        Compra.objects.filter(proveedor=proveedor)
        .select_related('bodega_destino', 'usuario')
        .prefetch_related('detalles', 'detalles__producto')
        .order_by('-fecha')
    )

    # 2. Calcular Métricas (KPIs)
    metricas = compras.aggregate(
        total_comprado=Sum('total'),    # Cuánto dinero le hemos dado a este proveedor
        total_facturas=Count('id'),     # Cuántas veces le hemos comprado
        ultima_compra=Max('fecha')      # Cuándo fue la última vez
    )

    ctx.update({
        "proveedor": proveedor,
        "compras": compras,
        "metricas": metricas,
        "titulo": f"Ficha: {proveedor.nombre}"
    })
    return render(request, "miapp/gestion/proveedor_detail.html", ctx)



@never_cache
@login_required
@requiere_bodega_o_admin
def proveedor_crear(request):
    return _procesar_proveedor(request, pk=None)

@never_cache
@login_required
@requiere_bodega_o_admin # CORREGIDO: Bodega puede editar proveedores para corregir typos
def proveedor_editar(request, pk):
    return _procesar_proveedor(request, pk=pk)

def _procesar_proveedor(request, pk):
    ctx = _get_context_base(request)
    instance = get_object_or_404(Proveedor, pk=pk) if pk else None
    modo = "Editar" if pk else "Crear"

    if request.method == "POST":
        form = ProveedorForm(request.POST, instance=instance)
        if form.is_valid():
            prov = form.save()
            messages.success(request, f"Proveedor '{prov.nombre}' guardado.")
            return redirect("miapp:proveedores_gestion")
        else:
            messages.error(request, "Error en el formulario.")
    else:
        form = ProveedorForm(instance=instance, initial={'es_activo': True} if not pk else None)

    ctx.update({
        "titulo": f"{modo} Proveedor",
        "form": form,
        "modo": modo
    })
    return render(request, "miapp/gestion/proveedor_form.html", ctx)


# ============================================================
# GESTIÓN DE CLIENTES (Aquí SÍ es Ventas o Admin)
# ============================================================

@never_cache
@login_required
@requiere_ventas_o_admin
def clientes_gestion(request):
    ctx = _get_context_base(request)
    
    q = request.GET.get("q", "").strip()
    f_tipo = request.GET.get("f_tipo", "")
    f_estado = request.GET.get("f_estado", "")
    
    filtros = Q()
    if q:
        filtros &= (Q(nombres__icontains=q) | Q(apellidos__icontains=q) | 
                    Q(numero_identificacion__icontains=q) | Q(codigo__icontains=q))
    
    if f_tipo: filtros &= Q(tipo_cliente_id=f_tipo)
    if f_estado == 'activos': filtros &= Q(es_activo=True)
    elif f_estado == 'inactivos': filtros &= Q(es_activo=False)

    items = (
        Cliente.objects.filter(filtros)
        .select_related('tipo_cliente', 'pais')
        .annotate(total_pedidos=Count('pedidos'))
        .order_by('-fecha_creacion')
    )

    ctx.update({
        "titulo": "Cartera Global de Clientes",
        "items": items,
        "tipos": TipoCliente.objects.filter(es_activo=True),
        "filtros": {"q": q, "f_tipo": f_tipo, "f_estado": f_estado}
    })
    return render(request, "miapp/gestion/clientes_list.html", ctx)

@never_cache
@login_required
@requiere_ventas_o_admin
def cliente_detalle(request, pk):
    ctx = _get_context_base(request)
    cliente = get_object_or_404(Cliente, pk=pk)
    
    # 1. Filtros de pedidos
    q_ped = request.GET.get("q_ped", "").strip()
    f_estado = request.GET.get("f_estado", "")
    pedidos_qs = cliente.pedidos.select_related('estado_pedido').prefetch_related('detalles__producto')
    
    if q_ped: pedidos_qs = pedidos_qs.filter(codigo__icontains=q_ped)
    if f_estado: pedidos_qs = pedidos_qs.filter(estado_pedido_id=f_estado)
    pedidos = pedidos_qs.order_by('-fecha_creacion')

    # 2. Métricas
    metricas = cliente.pedidos.aggregate(
        total_gastado=Sum('total'),
        ticket_promedio=Avg('total'),
        ultima_vez=Max('fecha_creacion')
    )

    # 3. Top Productos
    top_productos = (
        DetallePedido.objects.filter(pedido__cliente=cliente)
        .values('producto__nombre', 'producto__codigo_sku')
        .annotate(total_qty=Sum('cantidad_solicitada'))
        .order_by('-total_qty')[:5]
    )

    ctx.update({
        "cliente": cliente,
        "pedidos": pedidos,
        "top_productos": top_productos,
        "metricas": metricas,
        "estados_pedido": EstadoPedido.objects.all().order_by('descripcion'),
        "filtros_ped": {"q_ped": q_ped, "f_estado": f_estado},
        "titulo": f"Ficha: {cliente.codigo}"
    })
    return render(request, "miapp/gestion/cliente_detail.html", ctx)

@never_cache
@login_required
@requiere_ventas_o_admin
def cliente_crear(request):
    return _procesar_cliente(request, pk=None)

@never_cache
@login_required
@requiere_ventas_o_admin
def cliente_editar(request, pk):
    return _procesar_cliente(request, pk=pk)

def _procesar_cliente(request, pk):
    ctx = _get_context_base(request)
    instance = get_object_or_404(Cliente, pk=pk) if pk else None
    modo = "Editar" if pk else "Crear"

    if request.method == "POST":
        form = ClienteForm(request.POST, instance=instance)
        if form.is_valid():
            cliente = form.save()
            messages.success(request, f"Cliente '{cliente}' guardado.")
            return redirect("miapp:clientes_gestion")
    else:
        form = ClienteForm(instance=instance, initial={'es_activo': True} if not pk else None)

    ctx.update({"titulo": f"{modo} Cliente", "form": form, "modo": modo})
    return render(request, "miapp/gestion/cliente_form.html", ctx)