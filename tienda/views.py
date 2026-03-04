from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Q, Sum, Count, Avg, F
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone


from miapp.models import (
    Producto, Categoria, Marca, Pedido, InventarioProducto, 
    Cliente, TipoCliente, Pais, TipoAlmacenamiento, ClaseProducto,
    EstadoPedido, DetallePedido
)
from .models import Carrito, ItemCarrito, Favorito, DireccionEnvio, MetodoPago


def validador_cedula(texto):
    
    if not texto or not texto.isdigit() or len(texto) != 10:
        return False
    provincia = int(texto[0:2])
    if provincia < 1 or provincia > 24:
        return False
    tercer_digito = int(texto[2])
    if tercer_digito >= 6:
        return False
    coeficientes = [2, 1, 2, 1, 2, 1, 2, 1, 2]
    total = 0
    for i in range(9):
        valor = int(texto[i]) * coeficientes[i]
        if valor > 9: valor -= 9
        total += valor
    decena_superior = total - (total % 10) + 10 if total % 10 != 0 else total
    digito_verificador = decena_superior - total
    if digito_verificador == 10: digito_verificador = 0
    return digito_verificador == int(texto[9])



def index(request):
    return render(request, 'tienda/index.html')


def registro_cliente(request):
    if request.method == "POST":
        nombre = request.POST.get("nombre")
        apellido = request.POST.get("apellido")
        email = request.POST.get("email")
        password = request.POST.get("password")
        cedula = request.POST.get("cedula") 
        telefono = request.POST.get("telefono")

        
        if not validador_cedula(cedula):
            messages.error(request, "La cédula ingresada no es válida en Ecuador.")
            return render(request, "tienda/registro.html", locals())

        if not telefono.isdigit():
            messages.error(request, "El teléfono solo debe contener números.")
            return render(request, "tienda/registro.html", locals())
            
        if User.objects.filter(username=email).exists():
            messages.error(request, "Este correo ya está registrado.")
            return redirect("tienda:registro")
        
        if Cliente.objects.filter(numero_identificacion=cedula).exists():
             messages.error(request, "Ya existe un cliente registrado con esta cédula.")
             return redirect("tienda:registro")

      
        try:
            with transaction.atomic(): 
                user = User.objects.create_user(
                    username=email, email=email, password=password,
                    first_name=nombre, last_name=apellido
                )
                tipo_consumidor, _ = TipoCliente.objects.get_or_create(
                    codigo='CONSUMIDOR_FINAL', defaults={'descripcion': 'Cliente Web'}
                )
                pais_default, _ = Pais.objects.get_or_create(
                    nombre="Ecuador", defaults={'codigo_iso': 'EC', 'es_activo': True}
                )
                Cliente.objects.create(
                    nombres=nombre, apellidos=apellido, correo=email,
                    numero_identificacion=cedula, telefono=telefono,            
                    tipo_cliente=tipo_consumidor, pais=pais_default,
                    direccion="Dirección pendiente", es_activo=True
                )
                login(request, user)
                messages.success(request, f"¡Bienvenido {nombre}! Cuenta creada exitosamente.")
                return redirect("tienda:catalogo")

        except Exception as e:
            messages.error(request, f"Error del sistema: {str(e)}")
            return redirect("tienda:registro")

    return render(request, "tienda/registro.html")

def login_cliente(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect("tienda:catalogo")
        else:
            messages.error(request, "Usuario o contraseña incorrectos.")
    else:
        form = AuthenticationForm()
    return render(request, "tienda/login.html", {"form": form})

def logout_cliente(request):
    logout(request)
    return redirect("tienda:inicio")


def catalogo(request):
   
    productos = Producto.objects.filter(es_activo=True)\
        .annotate(
            total_ventas=Count('detalles_pedido', distinct=True) 
        )\
        .prefetch_related('imagenes')

  
    q = request.GET.get('q')
    if q:
        productos = productos.filter(
            Q(nombre__icontains=q) | 
            Q(descripcion__icontains=q) |
            Q(codigo_sku__icontains=q)
        )

   
    cats_ids = request.GET.getlist('categoria')
    if cats_ids:
        productos = productos.filter(categoria_id__in=cats_ids)

    marcas_ids = request.GET.getlist('marca')
    if marcas_ids:
        productos = productos.filter(marca_id__in=marcas_ids)

   
    almacen_ids = request.GET.getlist('almacenamiento')
    if almacen_ids:
        productos = productos.filter(tipo_almacenamiento_id__in=almacen_ids)
    
    clase_ids = request.GET.getlist('clase')
    if clase_ids:
        productos = productos.filter(clase_producto_id__in=clase_ids)

  
    p_min = request.GET.get('min')
    p_max = request.GET.get('max')
    if p_min:
        try: productos = productos.filter(precio_venta__gte=p_min)
        except: pass
    if p_max:
        try: productos = productos.filter(precio_venta__lte=p_max)
        except: pass

    if request.GET.get('stock') == '1':
        productos = productos.filter(inventarios__stock_actual__gt=0).distinct()

    if request.GET.get('tendencia') == 'bestseller':
        productos = productos.filter(total_ventas__gt=0)

  
    orden = request.GET.get('orden')
    if orden == 'precio_asc':
        productos = productos.order_by('precio_venta')
    elif orden == 'precio_desc':
        productos = productos.order_by('-precio_venta')
    elif orden == 'ventas_desc':
        productos = productos.order_by('-total_ventas')
    else:
       
        productos = productos.order_by('-fecha_creacion')

    filtro_base = Q(productos__es_activo=True, productos__es_publico=True)

    categorias_con_datos = Categoria.objects.filter(es_activo=True).annotate(
        total_productos=Count('productos', filter=filtro_base)
    ).order_by('nombre')

    marcas_con_datos = Marca.objects.filter(es_activo=True).annotate(
        total_productos=Count('productos', filter=filtro_base)
    ).order_by('nombre')
    
    almacen_con_datos = TipoAlmacenamiento.objects.filter(es_activo=True).annotate(
        total_productos=Count('productos', filter=filtro_base)
    )

    return render(request, 'tienda/catalogo.html', {
        'productos': productos.distinct(),
        'categorias': categorias_con_datos,
        'marcas': marcas_con_datos,
        'tipos_almacenamiento': almacen_con_datos,
        'clases': ClaseProducto.objects.filter(es_activo=True),
    })



def producto_detalle(request, producto_id):
    
    producto = get_object_or_404(
        Producto.objects.prefetch_related('imagenes'), 
        pk=producto_id
    )

    stock_total = InventarioProducto.objects.filter(producto=producto).aggregate(total=Sum('stock_actual'))['total'] or 0

    relacionados = Producto.objects.filter(
        categoria=producto.categoria, 
        es_publico=True, 
        es_activo=True
    ).exclude(id=producto_id)[:4]

    es_favorito = False
    if request.user.is_authenticated:
        es_favorito = Favorito.objects.filter(usuario=request.user, producto=producto).exists()

    return render(request, 'tienda/producto_detalle.html', {
        'producto': producto,
        'stock_total': stock_total,
        'relacionados': relacionados,
        'es_favorito': es_favorito
    })

def agregar_carrito(request, producto_id):
  
    if not request.user.is_authenticated:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
             return JsonResponse({'error': 'Debes iniciar sesión'}, status=401)
        messages.warning(request, "Inicia sesión para comprar.")
        return redirect('tienda:login')

    producto = get_object_or_404(Producto, id=producto_id)
    
    try:
        cantidad_solicitada = int(request.POST.get('cantidad', 1))
    except ValueError:
        cantidad_solicitada = 1
    if cantidad_solicitada < 1: cantidad_solicitada = 1

   
    stock_total = InventarioProducto.objects.filter(producto=producto).aggregate(total=Sum('stock_actual'))['total'] or 0
    
    carrito, _ = Carrito.objects.get_or_create(usuario=request.user)
    item, created = ItemCarrito.objects.get_or_create(carrito=carrito, producto=producto)
    
    cantidad_en_carrito = item.cantidad if not created else 0
    cantidad_final = cantidad_en_carrito + cantidad_solicitada

  

    if not created:
        item.cantidad += cantidad_solicitada
    else:
        item.cantidad = cantidad_solicitada
    item.save()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'success',
            'message': f'{producto.nombre} agregado al carrito',
            'cart_total': carrito.total_items 
        })

    messages.success(request, f"{producto.nombre} añadido al carrito.")
    return redirect(request.META.get('HTTP_REFERER', 'tienda:catalogo'))

@login_required
def ver_carrito(request):
    carrito, _ = Carrito.objects.get_or_create(usuario=request.user)
    items = carrito.items.all().select_related('producto')
    return render(request, 'tienda/carrito.html', {'carrito': carrito, 'items': items})

@login_required
def eliminar_del_carrito(request, item_id):
    item = get_object_or_404(ItemCarrito, id=item_id, carrito__usuario=request.user)
    nombre_producto = item.producto.nombre
    item.delete()
    messages.warning(request, f"{nombre_producto} eliminado del carrito.")
    return redirect('tienda:ver_carrito')

@login_required
def actualizar_item_carrito(request, item_id):
    if request.method == 'POST':
        item = get_object_or_404(ItemCarrito, id=item_id, carrito__usuario=request.user)
        accion = request.POST.get('accion')
        
        stock_total = InventarioProducto.objects.filter(producto=item.producto).aggregate(total=Sum('stock_actual'))['total'] or 0

        if accion == 'sumar':
            if item.cantidad < stock_total:
                item.cantidad += 1
                item.save()
            else:
                return JsonResponse({'status': 'error', 'message': 'Stock máximo alcanzado'})
        
        elif accion == 'restar':
            if item.cantidad > 1:
                item.cantidad -= 1
                item.save()
            else:
                pass

        return JsonResponse({
            'status': 'success',
            'cantidad': item.cantidad,
            'subtotal': item.subtotal,
            'carrito_total': item.carrito.total,
            'total_items': item.carrito.total_items
        })
    
    return JsonResponse({'status': 'error'}, status=400)



@login_required
def ver_favoritos(request):
    favoritos = Favorito.objects.filter(usuario=request.user).select_related('producto')
    return render(request, 'tienda/favoritos.html', {'favoritos': favoritos})

@login_required
def toggle_favorito(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)
    fav, created = Favorito.objects.get_or_create(usuario=request.user, producto=producto)
    
    if created:
        messages.success(request, f"¡{producto.nombre} guardado en favoritos!")
    else:
        fav.delete()
        messages.info(request, f"{producto.nombre} eliminado de favoritos.")
    
    return redirect(request.META.get('HTTP_REFERER', 'tienda:catalogo'))

@login_required
def mis_pedidos(request):
    pedidos = Pedido.objects.filter(usuario=request.user).order_by('-fecha_creacion')
    return render(request, 'tienda/mis_pedidos.html', {'pedidos': pedidos})


@login_required
def mi_perfil(request):
    cliente = getattr(request.user, 'cliente', None)
    
    if request.method == 'POST' and 'update_profile' in request.POST:
        try:
            with transaction.atomic():
                request.user.first_name = request.POST.get('nombre')
                request.user.last_name = request.POST.get('apellido')
                request.user.email = request.POST.get('email')
                request.user.save()

                if cliente:
                    cliente.nombres = request.POST.get('nombre')
                    cliente.apellidos = request.POST.get('apellido')
                    cliente.correo = request.POST.get('email')
                    cliente.telefono = request.POST.get('telefono')
                    cliente.numero_identificacion = request.POST.get('cedula')
                    cliente.save()
                
                messages.success(request, 'Perfil actualizado.')
        except Exception as e:
            messages.error(request, f'Error: {e}')
        return redirect('tienda:mi_perfil')

    direcciones = request.user.direcciones.filter(activa=True)
    tarjetas = request.user.metodos_pago.all().order_by('-es_predeterminado')

    return render(request, 'tienda/mi_perfil.html', {
        'cliente': cliente,
        'direcciones': direcciones,
        'tarjetas': tarjetas
    })


@login_required
def agregar_direccion(request):
    if request.method == 'POST':
        try:
            DireccionEnvio.objects.create(
                usuario=request.user,
                nombre_destinatario=request.POST.get('destinatario'),
                calle_principal=request.POST.get('calle_principal'),
                calle_secundaria=request.POST.get('calle_secundaria'),
                ciudad=request.POST.get('ciudad'),
                telefono=request.POST.get('telefono'),
                referencia=request.POST.get('referencia'),
                es_principal=True if request.POST.get('es_principal') else False
            )
            messages.success(request, "Dirección guardada correctamente.")
        except Exception as e:
            messages.error(request, f"Error al guardar la dirección: {e}")
    
    return redirect('tienda:mi_perfil')

@login_required
def eliminar_direccion(request, direccion_id):
    direccion = get_object_or_404(DireccionEnvio, id=direccion_id, usuario=request.user)
    direccion.activa = False 
    direccion.save()
    messages.warning(request, "Dirección eliminada.")
    return redirect('tienda:mi_perfil')


@login_required
def agregar_metodo_pago(request):
    if request.method == 'POST':
        numero_completo = request.POST.get('numero_tarjeta', '')
        ultimos_4 = numero_completo[-4:] if len(numero_completo) >= 4 else '0000'
        
        try:
            MetodoPago.objects.create(
                usuario=request.user,
                nombre_titular=request.POST.get('titular'),
                tipo=request.POST.get('tipo_tarjeta'),
                ultimos_digitos=ultimos_4,
                fecha_vencimiento=request.POST.get('vencimiento'),
                es_predeterminado=True
            )
            messages.success(request, "Tarjeta agregada exitosamente.")
        except Exception as e:
            messages.error(request, f"Error al guardar tarjeta: {e}")
    
    return redirect('tienda:mi_perfil')

@login_required
def eliminar_metodo_pago(request, pago_id):
    tarjeta = get_object_or_404(MetodoPago, id=pago_id, usuario=request.user)
    tarjeta.delete()
    messages.warning(request, "Método de pago eliminado.")
    return redirect('tienda:mi_perfil')



@login_required
def checkout(request):
  
    carrito, _ = Carrito.objects.get_or_create(usuario=request.user)
    
  
    if carrito.total_items == 0:
        messages.warning(request, "Tu carrito está vacío.")
        return redirect('tienda:catalogo')
    direcciones = request.user.direcciones.filter(activa=True)
    tarjetas = request.user.metodos_pago.all()
    items = carrito.items.all().select_related('producto')

    return render(request, 'tienda/checkout.html', {
        'carrito': carrito,
        'items': items,
        'direcciones': direcciones,
        'tarjetas': tarjetas
    })

@login_required
def procesar_compra(request):
  
    if request.method != 'POST':
        return redirect('tienda:checkout')

    direccion_id = request.POST.get('direccion_id')
    pago_id = request.POST.get('pago_id')

    if not direccion_id or not pago_id:
        messages.error(request, "Por favor selecciona una dirección y un método de pago.")
        return redirect('tienda:checkout')

    carrito = get_object_or_404(Carrito, usuario=request.user)
    items = carrito.items.all().select_related('producto')

    if not items.exists():
        messages.error(request, "Tu carrito está vacío.")
        return redirect('tienda:catalogo')

    try:
        with transaction.atomic():
            cliente = Cliente.objects.filter(correo=request.user.email).first()
            if not cliente:
                tipo_web, _ = TipoCliente.objects.get_or_create(
                    codigo='CONSUMIDOR_FINAL', 
                    defaults={'descripcion': 'Cliente E-commerce', 'es_activo': True}
                )
                cliente = Cliente.objects.create(
                    nombres=request.user.first_name,
                    apellidos=request.user.last_name,
                    correo=request.user.email,
                    tipo_cliente=tipo_web,
                    es_activo=True,
                    direccion="Dirección Web"
                )

            estado_inicial = EstadoPedido.objects.get(codigo=EstadoPedido.CODIGO_SOLICITADO)

    
            pedido = Pedido.objects.create(
                cliente=cliente,
                usuario=request.user,
                estado_pedido=estado_inicial,
                origen=Pedido.OrigenPedido.WEB, 
                subtotal=carrito.total,
                total=carrito.total,
                codigo=f"WEB-{timezone.now().strftime('%Y%m%d%H%M')}"
            )

            
            for item in items:
                DetallePedido.objects.create(
                    pedido=pedido,
                    producto=item.producto,
                    cantidad_solicitada=item.cantidad,
                    cantidad_atendida=0,
                    precio_unitario=item.producto.precio_venta,
                    costo_unitario=item.producto.costo_compra,
                    estado_logistico=DetallePedido.EstadoLogistico.DISPONIBLE
                )
            
          
            carrito.items.all().delete()
            
            messages.success(request, "¡Pedido realizado! Tu orden está pendiente de preparación en bodega.")
            return redirect('tienda:compra_exitosa', pedido_id=pedido.id)

    except EstadoPedido.DoesNotExist:
        messages.error(request, "Error de configuración: El estado 'SOLICITADO' no existe en la base de datos.")
        return redirect('tienda:checkout')
    except Exception as e:
        messages.error(request, f"Error al procesar la compra: {str(e)}")
        return redirect('tienda:checkout')
    
    
@login_required
def compra_exitosa(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id, usuario=request.user)
    return render(request, 'tienda/compra_exitosa.html', {'pedido': pedido})


@login_required
def detalle_compra(request, pedido_id):
    
    pedido = get_object_or_404(Pedido, id=pedido_id, usuario=request.user)
    
  
    detalles = pedido.detalles.select_related('producto').prefetch_related('producto__imagenes')
    
    ctx = {
        'pedido': pedido,
        'detalles': detalles
    }
    return render(request, 'tienda/pedido_detalle.html', ctx)