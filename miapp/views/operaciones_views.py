# --- Python estándar ---
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
import json

# --- Django ---
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction, models
from django.db.models import Q, F
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

# --- Helpers ---
from .helpers import _get_context_base, requiere_bodega_o_admin

# --- Modelos ---
from ..models import (
    # Catálogos
    Producto, Categoria, Marca, Impuesto,
    TipoAlmacenamiento, ClaseProducto, PerfilCaducidad,ImagenProducto,

    # Actores
    Bodega, Proveedor, Cliente, PerfilUsuario,

    # Estados y tipos
    TipoMovimiento, EstadoLote, EstadoPedido,

    # Ubicación
    UbicacionFisica, ZonaAlmacenamiento,

    # Inventario
    InventarioProducto, StockLote, MovimientoInventario,

    # Compras
    Compra, DetalleCompra,

    # Pedidos
    Pedido, DetallePedido,

    # Transferencias
    TransferenciaInterna,
    DetalleTransferenciaInterna,
    DetalleTransferenciaLote,
)

# ==============================================================================
# 1. RECEPCIÓN DE MERCANCÍA (COMPRA)
# ==============================================================================
# miapp/views/operaciones_views.py
@login_required
def mov_entrada(request):
    """
    RECEPCIÓN DE MERCANCÍA (COMPRA) - TOLERANTE A ALERTAS:
    - Admin: Puede elegir bodega.
    - Bodeguero: Bloqueado a su bodega.
    - CALIDAD: 
        * VENCIDOS (<= Hoy) -> ERROR (Rechaza ingreso y hace rollback).
        * VIDA CORTA (< Límite) -> ADVERTENCIA (Permite ingreso, muestra alerta amarilla, NO borra tabla).
    """
    ctx = _get_context_base(request)
    
    # --- A. IDENTIFICACIÓN DE PERFIL Y ROL ---
    perfil = getattr(request.user, 'perfil', None)
    
    es_admin = request.user.is_superuser
    if perfil and perfil.rol_negocio == PerfilUsuario.RolNegocio.ADMIN_SISTEMA:
        es_admin = True
    
    es_bodeguero = perfil and perfil.rol_negocio == PerfilUsuario.RolNegocio.OPERADOR_OPERACIONES
    mi_bodega = perfil.bodega if (es_bodeguero and perfil) else None
    
    puede_recibir = es_admin or es_bodeguero

    if not puede_recibir:
        messages.error(request, "Acceso Denegado: No tienes permisos para recibir mercancía.")
        return redirect('miapp:inicio')

    if es_bodeguero and not mi_bodega:
        messages.error(request, "Configuración incompleta: Su usuario de bodeguero no tiene sede asignada.")
        return redirect('miapp:inicio')

    # --- B. PROCESAMIENTO (POST) ---
    if request.method == 'POST':
        try:
            with transaction.atomic():
                
                # 1. Validación Bodega
                if es_admin:
                    bodega_id_form = request.POST.get('bodega')
                    if not bodega_id_form:
                        raise ValidationError("Debe seleccionar una bodega de destino.")
                    bodega_destino = get_object_or_404(Bodega, pk=bodega_id_form)
                else:
                    bodega_destino = mi_bodega
                    enviado_id = request.POST.get('bodega')
                    if enviado_id and str(enviado_id) != str(mi_bodega.id):
                        raise ValidationError(f"Seguridad: Intento no autorizado en bodega ajena.")

                # 2. Validación Infraestructura
                if not ZonaAlmacenamiento.objects.filter(bodega=bodega_destino, es_activo=True).exists():
                     raise ValidationError(f"La bodega '{bodega_destino.nombre}' no tiene zonas de almacenamiento activas. Configure la infraestructura.")

                # 3. Cabecera Compra
                proveedor_id = request.POST.get('proveedor')
                ref_documento = request.POST.get('referencia')
                observacion = request.POST.get('observacion')
                
                if not proveedor_id: raise ValidationError("Seleccione un proveedor.")
                proveedor = get_object_or_404(Proveedor, pk=proveedor_id)

                nueva_compra = Compra.objects.create(
                    proveedor=proveedor,
                    bodega_destino=bodega_destino,
                    usuario=request.user,
                    numero_factura=ref_documento,
                    observacion=observacion,
                    total=0
                )

                # 4. Detalle
                productos_ids = request.POST.getlist('producto_id[]')
                cantidades = request.POST.getlist('cantidad[]')
                costos = request.POST.getlist('costo[]') 
                f_caducidades = request.POST.getlist('fecha_caducidad[]')

                if not productos_ids: raise ValidationError("La compra está vacía.")

                tm_compra, created = TipoMovimiento.objects.get_or_create(
                    codigo=TipoMovimiento.CODIGO_COMPRA,
                    defaults={
                        'descripcion': 'Recepción de Compra', 
                        'es_entrada': True, 
                        'es_salida': False, 
                        'afecta_stock': True
                    }
                )
                
                if not created and (tm_compra.es_salida or not tm_compra.es_entrada):
                    tm_compra.es_entrada = True
                    tm_compra.es_salida = False
                    tm_compra.save()
                
                est_disponible, _ = EstadoLote.objects.get_or_create(
                    codigo=EstadoLote.CODIGO_DISPONIBLE,
                    defaults={'es_vendible': True}
                )

                total_acumulado = 0

                for i, prod_id in enumerate(productos_ids):
                    if not prod_id: continue
                    
                    producto = Producto.objects.get(pk=prod_id)
                    cant = int(cantidades[i])
                    costo_unitario = Decimal(costos[i])
                    
                    # Actualizar Costo Maestro
                    if producto.costo_compra != costo_unitario:
                        producto.costo_compra = costo_unitario
                        producto.save(update_fields=['costo_compra'])

                    # ==========================================================
                    # LÓGICA DE CADUCIDAD Y CALIDAD (MODIFICADA)
                    # ==========================================================
                    caducidad_str = f_caducidades[i] if len(f_caducidades) > i else None
                    fecha_vencimiento = None
                    
                    if producto.perfil_caducidad and producto.perfil_caducidad.requiere_caducidad:
                        if not caducidad_str:
                            raise ValidationError(f"El producto '{producto.nombre}' requiere fecha de caducidad obligatoria.")
                        
                        try:
                            fecha_vencimiento = datetime.strptime(caducidad_str, '%Y-%m-%d').date()
                        except ValueError:
                            raise ValidationError(f"Formato de fecha inválido para '{producto.nombre}'.")

                        hoy = timezone.now().date()
                        
                        # CASO 1: VENCIDO (BLOQUEO TOTAL)
                        if fecha_vencimiento <= hoy:
                            raise ValidationError(f"RECHAZADO: El producto '{producto.nombre}' ya está vencido ({fecha_vencimiento}). No se puede recibir.")

                        # CASO 2: VIDA CORTA (SOLO ADVERTENCIA - NO DETIENE EL GUARDADO)
                        dias_bloqueo = producto.perfil_caducidad.dias_bloqueo_previo or 0
                        margen_minimo = dias_bloqueo + 7 
                        limite_aceptacion = hoy + timedelta(days=margen_minimo)
                        
                        if fecha_vencimiento < limite_aceptacion:
                            dias_restantes = (fecha_vencimiento - hoy).days
                            # IMPORTANTE: Usamos messages.warning en lugar de raise ValidationError
                            # Esto permite que el código siga ejecutándose y guarde la compra.
                            messages.warning(request, 
                                f"Atención de Calidad: Se ingresó '{producto.nombre}' pero tiene vida útil corta ({dias_restantes} días). Priorice su salida (FEFO)."
                            )
                    
                    elif not fecha_vencimiento:
                        fecha_vencimiento = timezone.now().date() + timedelta(days=365)
                    # ==========================================================

                    # Crear Lote Físico
                    lote_codigo = f"L{timezone.now().strftime('%y%m%d')}-{producto.id}-{nueva_compra.id}-{i}"
                    
                    nuevo_lote = StockLote(
                        producto=producto,
                        lote=lote_codigo,
                        fecha_caducidad=fecha_vencimiento,
                        cantidad_disponible=cant,
                        costo_compra_lote=costo_unitario, 
                        proveedor=proveedor,
                        estado_lote=est_disponible,
                        fecha_entrada=timezone.now()
                    )
                    nuevo_lote._bodega_destino = bodega_destino 
                    nuevo_lote.save()

                    # Detalle Compra
                    DetalleCompra.objects.create(
                        compra=nueva_compra, producto=producto, cantidad=cant,
                        costo_unitario=costo_unitario, total_linea=cant * costo_unitario,
                        lote_generado=nuevo_lote
                    )
                    total_acumulado += (cant * costo_unitario)

                    # Inventario Global
                    inv, _ = InventarioProducto.objects.get_or_create(
                        producto=producto, bodega=bodega_destino,
                        defaults={'stock_actual': 0}
                    )
                    stock_antes = inv.stock_actual
                    inv.stock_actual += cant
                    inv.fecha_ultimo_movimiento = timezone.now()
                    inv.save()

                    # Kardex
                    MovimientoInventario.objects.create(
                        inventario=inv,
                        stock_lote=nuevo_lote,
                        tipo_movimiento=tm_compra,
                        usuario=request.user,
                        bodega_destino=bodega_destino,
                        cantidad=cant,
                        stock_antes=stock_antes,
                        stock_despues=inv.stock_actual,
                        valor_unitario=costo_unitario,
                        valor_total=cant * costo_unitario,
                        motivo=f"Recepción Compra #{nueva_compra.id}"
                    )

                # Finalizar Compra
                nueva_compra.total = total_acumulado
                nueva_compra.save()

            messages.success(request, f"Recepción exitosa en {bodega_destino.nombre}. Ref: {ref_documento}")
            return redirect('miapp:inventario_global_consulta')

        except ValidationError as e:
             messages.error(request, f"Error de Validación: {e.message}")
        except Exception as e:
            messages.error(request, f"Error del Sistema: {str(e)}")

    # --- C. LÓGICA GET ---
    if es_admin:
        productos_disponibles = Producto.objects.filter(es_activo=True)
        bodegas_list = Bodega.objects.filter(es_activo=True)
    else:
        tipos_validos = ZonaAlmacenamiento.objects.filter(
            bodega=mi_bodega, 
            es_activo=True
        ).values_list('tipo_almacenamiento', flat=True).distinct()
        
        productos_disponibles = Producto.objects.filter(
            es_activo=True,
            tipo_almacenamiento__in=tipos_validos
        )
        bodegas_list = [mi_bodega]

    ctx.update({
        'titulo': "Recepción de Mercancía",
        'bodegas': bodegas_list,
        'bodega_fija': None if es_admin else mi_bodega,
        'es_admin': es_admin,
        'proveedores': Proveedor.objects.filter(es_activo=True),
        'productos': productos_disponibles, 
        
        # Contexto para Modal de Creación Rápida
        'perfiles_qc': PerfilCaducidad.objects.filter(es_activo=True),
        'categorias_qc': Categoria.objects.filter(es_activo=True),
        'marcas_qc': Marca.objects.filter(es_activo=True),
        'tipos_alm_qc': TipoAlmacenamiento.objects.filter(es_activo=True),
        'clases_qc': ClaseProducto.objects.filter(es_activo=True),
        'impuestos_qc': Impuesto.objects.filter(es_activo=True),
        'estrategias_qc': Producto.EstrategiaSalida.choices,
    })

    return render(request, "miapp/operaciones/ingreso_form.html", ctx)


@login_required
def mov_salida(request):
    """
    CONSOLA DE DESPACHO DESCENTRALIZADA E INTELIGENTE:
    - Admin: Posee visión global. Ve todos los pedidos y despacha usando el motor inteligente multibodega.
    - Bodeguero: Posee visión local. Solo ve pedidos que requieren productos existentes en SU bodega.
    """
    ctx = _get_context_base(request)
    perfil = getattr(request.user, 'perfil', None)
    
    # 1. Definición de Roles y Bodega de Sesión
    es_admin = request.user.is_superuser or (perfil and perfil.rol_negocio == PerfilUsuario.RolNegocio.ADMIN_SISTEMA)
    mi_bodega = perfil.bodega if perfil else None

    # Bloqueo de seguridad: Bodegueros sin sede asignada no pueden operar
    if not es_admin and not mi_bodega:
        messages.error(request, "Error de Perfil: No tienes una bodega física asignada para despachar.")
        return redirect('miapp:inicio')

    # --- B. PROCESAMIENTO DE AUTORIZACIÓN (POST) ---
    if request.method == 'POST':
        pedido_id = request.POST.get('pedido_id')
        pedido = get_object_or_404(Pedido, pk=pedido_id)
        
        try:
            with transaction.atomic():
                if es_admin:
                    # El Administrador ejecuta el barrido automático por todas las bodegas
                    pedido.procesar_despacho_completo(request.user)
                    messages.success(request, f"Administrador: Pedido {pedido.codigo} despachado globalmente.")
                else:
                    # El Bodeguero firma la salida únicamente de los productos en SU bodega
                    hizo_despacho = pedido.autorizar_salida_fraccionada(request.user, mi_bodega)
                    
                    if hizo_despacho:
                        pedido.refresh_from_db()
                        if pedido.estado_pedido.codigo == EstadoPedido.CODIGO_ENTREGADO:
                            messages.success(request, f"Pedido {pedido.codigo} completado totalmente tras tu despacho.")
                        else:
                            messages.info(request, f"Salida autorizada desde {mi_bodega.nombre}. El pedido continúa abierto por saldos en otras bodegas.")
                    else:
                        messages.warning(request, f"Operación omitida: No se encontró stock pendiente en {mi_bodega.nombre} para este pedido.")
                    
            return redirect('miapp:mov_salida')

        except ValidationError as e:
            messages.error(request, f"Aviso de Validación: {str(e)}")
        except Exception as e:
            messages.error(request, f"Error Crítico de Sistema: {str(e)}")

    # --- C. VISTA DE PEDIDOS FILTRADOS (GET) ---
    # Definimos estados que requieren acción logística
    estados_pendientes = [
        EstadoPedido.CODIGO_SOLICITADO, 
        EstadoPedido.CODIGO_PREPARACION,
        getattr(EstadoPedido, 'CODIGO_PARCIAL', 'ENTREGA_PARCIAL'),
        getattr(EstadoPedido, 'CODIGO_BACKORDER', 'BACKORDER')
    ]
    
    # Consulta base con optimización de relaciones
    pedidos = Pedido.objects.filter(
        estado_pedido__codigo__in=estados_pendientes
    ).select_related('cliente', 'estado_pedido').order_by('fecha_creacion')

    # === FILTRO DE SEGMENTACIÓN LOGÍSTICA ===
    if not es_admin:
        # El Bodeguero solo ve pedidos donde:
        # 1. Algún producto solicitado esté vinculado a SU bodega en InventarioProducto.
        # 2. SU bodega tenga existencias físicas reales (stock_actual > 0).
        pedidos = pedidos.filter(
            detalles__producto__inventarios__bodega=mi_bodega,
            detalles__producto__inventarios__stock_actual__gt=0
        ).distinct() # .distinct() es vital para evitar duplicados por el join de detalles
        
    # Filtro de búsqueda (Buscador superior)
    q = request.GET.get('q')
    if q:
        pedidos = pedidos.filter(
            Q(codigo__icontains=q) | 
            Q(cliente__nombres__icontains=q) | 
            Q(cliente__apellidos__icontains=q) |
            Q(cliente__numero_identificacion__icontains=q)
        ).distinct()

    ctx.update({
        'pedidos': pedidos,
        'mi_bodega': mi_bodega,
        'es_admin': es_admin,
        'titulo': "Control de Despachos Global" if es_admin else f"Despachos Pendientes - {mi_bodega.nombre}"
    })
    
    return render(request, "miapp/operaciones/salida_list.html", ctx)

@login_required
def pedido_create(request):
    """
    REGISTRO DE PEDIDOS (ERP):
    - Solo Vendedores y Administradores pueden generar ventas.
    - El Bodeguero queda excluido de esta función para mantener la separación de funciones.
    """
    ctx = _get_context_base(request)
    perfil = getattr(request.user, 'perfil', None)
    
    # 1. Validación de Seguridad por Rol
    es_admin = request.user.is_superuser or (perfil and perfil.rol_negocio == PerfilUsuario.RolNegocio.ADMIN_SISTEMA)
    es_vendedor = perfil and perfil.rol_negocio == PerfilUsuario.RolNegocio.VENDEDOR
    
    # Si no es admin ni vendedor, bloqueamos el acceso
    if not (es_admin or es_vendedor):
        messages.error(request, "Acceso Denegado: Su perfil no tiene permisos para generar órdenes de venta.")
        return redirect('miapp:inicio')

    # --- B. PROCESAMIENTO (POST) ---
    if request.method == 'POST':
        try:
            with transaction.atomic():
                cliente_id = request.POST.get('cliente')
                observaciones = request.POST.get('observaciones')
                
                # Opcional: Si tu formulario envía la bodega seleccionada, captúrala aquí.
                # bodega_origen_id = request.POST.get('bodega')
                
                if not cliente_id: 
                    raise ValidationError("Debe seleccionar un cliente para procesar la venta.")
                
                cliente = get_object_or_404(Cliente, pk=cliente_id)
                
                # Obtener estado inicial 'SOLICITADO'
                estado_solicitado, _ = EstadoPedido.objects.get_or_create(
                    codigo=EstadoPedido.CODIGO_SOLICITADO, 
                    defaults={'descripcion': 'Solicitado'}
                )

                # Crear el Pedido (Venta agnóstica a bodega física por defecto, o vinculada si lo deseas)
                nuevo_pedido = Pedido.objects.create(
                    cliente=cliente,
                    usuario=request.user,
                    estado_pedido=estado_solicitado,
                    origen=Pedido.OrigenPedido.ERP,
                    observaciones=observaciones.strip() if observaciones else None,
                    total=0,
                    # Si tu modelo tiene el campo 'bodega_origen', descomenta esto:
                    # bodega_origen_id=bodega_origen_id 
                )

                # Procesar productos del detalle
                productos_ids = request.POST.getlist('producto_id[]')
                cantidades = request.POST.getlist('cantidad[]')
                precios = request.POST.getlist('precio[]') 

                if not productos_ids: 
                    raise ValidationError("La orden de venta debe contener al menos un producto.")

                for i in range(len(productos_ids)):
                    if not productos_ids[i]: continue
                        
                    DetallePedido.objects.create(
                        pedido=nuevo_pedido,
                        producto_id=productos_ids[i],
                        cantidad_solicitada=int(cantidades[i]),
                        precio_unitario=Decimal(precios[i]),
                    )

                # Recalcular totales financieros y rentabilidad
                nuevo_pedido.recalcular_totales()
                
            messages.success(request, f"Venta {nuevo_pedido.codigo} registrada. Pase a despacho para autorizar la salida.")
            return redirect('miapp:pedidos_consulta')

        except ValidationError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f"Error crítico en la venta: {str(e)}")

    # --- C. LÓGICA GET PARA EL FORMULARIO (CORREGIDA) ---
    
    # Recuperamos las bodegas activas para llenar el select del HTML
    bodegas_disponibles = Bodega.objects.filter(es_activo=True)

    ctx.update({
        'titulo': "Generar Nueva Orden de Venta",
        'clientes': Cliente.objects.filter(es_activo=True),
        'productos': Producto.objects.filter(es_activo=True),
        'bodegas': bodegas_disponibles,  # <--- AQUÍ ESTABA EL FALTANTE
        'es_admin': es_admin
    })
    return render(request, "miapp/operaciones/pedido_form.html", ctx)


# ==============================================================================
# 4. SOLICITUD INTELIGENTE (PULL / "COMPLETAR CANTIDAD")
# ==============================================================================
from django.db.models import F # Asegúrate de importar F arriba

@login_required
def transferencia_solicitar(request):
    """
    CEREBRO LOGÍSTICO (CORREGIDO PARA SALDOS PENDIENTES):
    Calcula dinámicamente: Cantidad Total - Cantidad Ya Atendida.
    Solo solicita el remanente a las otras bodegas.
    """
    ctx = _get_context_base(request)
    perfil = getattr(request.user, 'perfil', None)
    es_admin = request.user.is_superuser or (perfil and perfil.rol_negocio == 'ADMIN_SISTEMA')
    
    # --- LÓGICA POST (PROCESAR LA SOLICITUD) ---
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Capturamos datos del formulario
                producto_id = request.POST.get('producto_id')
                pedido_id = request.POST.get('pedido_id')
                cantidad = request.POST.get('cantidad') # Aquí viene el valor calculado
                origen_id = request.POST.get('origen_id')
                destino_id = request.POST.get('destino_id')

                if not all([producto_id, pedido_id, origen_id, destino_id]):
                    raise Exception("Datos incompletos para la transferencia.")

                # Validamos que la cantidad sea un número válido
                cant_solicitar = int(cantidad)
                if cant_solicitar <= 0:
                    raise Exception("La cantidad a solicitar debe ser mayor a 0.")

                obj_origen = Bodega.objects.get(pk=origen_id)
                obj_destino = Bodega.objects.get(pk=destino_id)
                obj_pedido = Pedido.objects.get(pk=pedido_id)

                # Validar Stock en el Origen antes de crear la solicitud (Doble check)
                # Esto evita crear transferencias que nacerán muertas
                stock_disponible_origen = StockLote.objects.filter(
                    producto_id=producto_id,
                    ubicacion__rack__zona__bodega=obj_origen,
                    estado_lote__es_vendible=True,
                    cantidad_disponible__gt=0
                ).aggregate(total=models.Sum('cantidad_disponible'))['total'] or 0

                if stock_disponible_origen < cant_solicitar:
                     raise Exception(f"La Bodega {obj_origen.nombre} solo tiene {stock_disponible_origen} unid. (Tú pides {cant_solicitar})")

                # Crear Transferencia
                trf = TransferenciaInterna.objects.create(
                    tipo=TransferenciaInterna.Tipo.POR_PEDIDO, 
                    pedido=obj_pedido,
                    bodega_origen=obj_origen,
                    bodega_destino=obj_destino,
                    usuario_solicita=request.user,
                    estado=TransferenciaInterna.Estado.SOLICITADA,
                    observaciones=f"Auto-Refill: Faltante de Pedido {obj_pedido.codigo}"
                )
                
                DetalleTransferenciaInterna.objects.create(
                    transferencia=trf,
                    producto_id=producto_id,
                    cantidad_solicitada=cant_solicitar
                )

                messages.success(request, f" Solicitud enviada: {cant_solicitar} unid. desde {obj_origen.nombre}.")
                return redirect('miapp:transferencia_solicitar')

        except Exception as e:
            messages.error(request, f"No se pudo procesar: {str(e)}")


    # --- LÓGICA GET (BUSCAR FALTANTES REALES) ---
    filtro_bodega = {'pedido__bodega_origen': perfil.bodega} if (not es_admin and perfil.bodega) else {}
    
    # 1. Filtramos pedidos incompletos
    detalles_pendientes = DetallePedido.objects.filter(
        pedido__estado_pedido__codigo__in=['SOLICITADO', 'PREPARACION', 'ENTREGA_PARCIAL', 'BACKORDER'],
        cantidad_atendida__lt=F('cantidad_solicitada'),
        **filtro_bodega
    ).select_related('producto', 'pedido', 'pedido__bodega_origen', 'pedido__cliente').order_by('pedido__id')

    # 2. Procesamos cada línea para calcular el saldo exacto
    for det in detalles_pendientes:
        # === CORRECCIÓN MAESTRA ===
        # Calculamos lo que falta REALMENTE.
        # Si pidieron 2 y ya despachaste 1, saldo es 1.
        saldo = det.cantidad_solicitada - det.cantidad_atendida
        
        # Sobrescribimos el atributo para que el HTML reciba el "1" y no el "2"
        det.cantidad_solicitada = saldo 

        # Buscamos quién tiene ese saldo
        bodega_dest = det.pedido.bodega_origen 
        
        # Sugerimos solo bodegas que tengan stock >= al saldo que necesitamos
        # (Opcional: puedes quitar stock_actual__gte=saldo si quieres permitir parciales de parciales)
        det.fuentes_sugeridas = InventarioProducto.objects.filter(
            producto=det.producto, 
            stock_actual__gt=0, 
            bodega__es_activo=True
        ).exclude(bodega=bodega_dest).select_related('bodega').order_by('-stock_actual')
        
        det.bodega_destino_calculada = bodega_dest

    ctx.update({
        'sugerencias_deficit': detalles_pendientes,
        'titulo': "Gestión Inteligente de Stock (Saldos)"
    })
    return render(request, "miapp/operaciones/transferencia_solicitud.html", ctx)

@login_required
def transferencia_despachar(request, trf_id):
    """
    CONSOLA DEL BODEGUERO DE ORIGEN:
    Ejecuta el movimiento físico del Kardex para sacar la mercadería.
    """
    trf = get_object_or_404(TransferenciaInterna, pk=trf_id)
    
    # Seguridad: Solo el origen puede despachar
    perfil = getattr(request.user, 'perfil', None)
    if not request.user.is_superuser and perfil.bodega != trf.bodega_origen:
        messages.error(request, "No tienes permiso para despachar desde esta bodega.")
        return redirect('miapp:transferencias_consulta')

    if request.method == 'POST':
        try:
            # Usamos el método que ya tienes en el modelo TransferenciaInterna
            # Este método es el que CREA el MovimientoInventario (Kardex)
            trf.ejecutar_despacho_fisico(request.user)
            messages.success(request, f" Transferencia {trf.codigo} despachada. Stock descontado de origen.")
        except Exception as e:
            messages.error(request, f"Error al despachar: {str(e)}")
            
    return redirect('miapp:transferencias_consulta')
# miapp/views/operaciones_views.py

@login_required
def transferencia_recibir(request, trf_id):

    trf = get_object_or_404(TransferenciaInterna, pk=trf_id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Iteramos sobre los lotes que vienen en camino
                for detalle_prod in trf.detalles.all():
                    for lote_link in detalle_prod.lotes_asignados.all():
                        # Confirmamos la recepción (suma stock en destino)
                        lote_link.confirmar_recepcion_automatica(request.user)
                
                messages.success(request, f" Stock recibido. Ahora está disponible en {trf.bodega_destino.nombre}")
        except Exception as e:
            messages.error(request, f"Error al recibir: {str(e)}")
            
    return redirect('miapp:transferencias_consulta')


# miapp/views/operaciones_views.py

@login_required
def transferencia_ejecutar_despacho(request, trf_id):
    """
    LIBERACIÓN DE STOCK (BODEGA ORIGEN):
    Resta físicamente el producto del inventario de origen.
    """
    trf = get_object_or_404(TransferenciaInterna, pk=trf_id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                trf.ejecutar_despacho_fisico(request.user)
                
                messages.success(request, f" Stock liberado de {trf.bodega_origen.nombre}. La carga está en tránsito.")
        except Exception as e:
            messages.error(request, f"Error al liberar stock: {str(e)}")
            
    return redirect('miapp:transferencias_consulta')

@login_required
def transferencia_ejecutar_recepcion(request, trf_id):
    """
    INGRESO DE STOCK (BODEGA DESTINO):
    Suma físicamente el producto al inventario de la bodega que solicitó.
    """
    trf = get_object_or_404(TransferenciaInterna, pk=trf_id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Validamos que existan detalles antes de recibir
                detalles = trf.detalles.all()
                if not detalles.exists():
                    raise Exception("La transferencia no tiene ítems registrados para recibir.")

                for detalle_prod in detalles:
                    # Buscamos los lotes que fueron asignados en el despacho
                    lotes_vinculados = detalle_prod.lotes_asignados.all()
                    
                    if not lotes_vinculados.exists():
                        raise Exception(f"No hay lotes despachados para el producto {detalle_prod.producto.nombre}.")

                    for lote_link in lotes_vinculados:
                        # Este método crea el nuevo lote en la Bodega Central y registra el Kardex
                        lote_link.confirmar_recepcion_automatica(request.user)
                
                messages.success(request, f" Stock ingresado con éxito en {trf.bodega_destino.nombre}.")
        except Exception as e:
            messages.error(request, f"Error al ingresar stock: {str(e)}")
            
    return redirect('miapp:transferencias_consulta')
# miapp/views/consultas_views.py

@login_required
def transferencias_consulta(request):
    ctx = _get_context_base(request)
    perfil = getattr(request.user, 'perfil', None)
    
    # Si es un bodeguero, solo ve lo que sale de SU bodega o lo que entra a SU bodega
    if not request.user.is_superuser and perfil and perfil.bodega:
        query = TransferenciaInterna.objects.filter(
            models.Q(bodega_origen=perfil.bodega) | models.Q(bodega_destino=perfil.bodega)
        )
    else:
        query = TransferenciaInterna.objects.all()

    transferencias = query.select_related('bodega_origen', 'bodega_destino', 'usuario_solicita').order_by('-fecha_creacion')

    ctx.update({
        'transferencias': transferencias,
        'titulo': "Control de Movimientos Logísticos"
    })
    return render(request, 'miapp/operaciones/transferencia_list.html', ctx)

# ==============================================================================
# 5. TIPO 2: TRANSFERENCIA MANUAL (PUSH / "POR LOTE / ZONA DAÑADA")
# ==============================================================================
# miapp/views/operaciones_views.py
@login_required
@login_required
def transferencia_manual(request):
    """
    TRANSFERENCIA MANUAL (PUSH) - VERSIÓN ATÓMICA SEGURA
    Estrategia: Verificar Primero, Crear Después.
    """
    ctx = _get_context_base(request)
    perfil = getattr(request.user, 'perfil', None)
    
    # 1. GET: Cargar datos
    origen_id = request.GET.get('origen')
    bodegas = Bodega.objects.filter(es_activo=True)
    
    if not request.user.is_superuser and perfil and perfil.bodega:
        origen_id = perfil.bodega.id
        bodegas = [perfil.bodega]

    lotes_disponibles = []
    if origen_id:
        try:
            lotes_disponibles = StockLote.objects.filter(
                ubicacion__rack__zona__bodega_id=origen_id,
                cantidad_disponible__gt=0,
                estado_lote__es_vendible=True 
            ).select_related('producto', 'estado_lote', 'ubicacion').order_by('producto__nombre', 'fecha_caducidad')
        except Exception: pass

    # 2. POST: Procesar
    if request.method == 'POST':
        try:
            with transaction.atomic():
                bodega_dest_id = request.POST.get('bodega_destino')
                raw_ids = request.POST.getlist('lotes_seleccionados')
                lotes_ids = list(set(raw_ids)) # Limpieza inicial
                
                if not bodega_dest_id: raise Exception("Seleccione bodega de destino.")
                if not lotes_ids: raise Exception("No seleccionó lotes.")
                
                bodega_origen = Bodega.objects.get(pk=origen_id)
                bodega_destino = Bodega.objects.get(pk=bodega_dest_id)

                if bodega_origen == bodega_destino:
                    raise Exception("Origen y Destino no pueden ser iguales.")

                # === FASE 1: BLOQUEO Y VALIDACIÓN (Sin crear nada aún) ===
                lotes_validos = []
                
                for lid in lotes_ids:
                    # Bloqueamos el lote en la BD
                    l = StockLote.objects.select_for_update().get(pk=lid)
                    
                    # Revisamos si YA está en uso (Anti-Doble Clic)
                    en_uso = DetalleTransferenciaLote.objects.filter(
                        stock_lote_origen=l,
                        detalle__transferencia__estado__in=['SOLICITADA', 'EN_PREPARACION', 'DESPACHADA']
                    ).exists()
                    
                    if en_uso:
                        # Si encontramos uno usado, abortamos TODA la operación.
                        raise Exception(f"El lote {l.lote} ya se está transfiriendo en otra orden.")
                    
                    if l.cantidad_disponible <= 0:
                        raise Exception(f"El lote {l.lote} no tiene stock.")
                        
                    lotes_validos.append(l)

                # === FASE 2: CREACIÓN (Solo si pasamos la Fase 1) ===
                trf = TransferenciaInterna.objects.create(
                    tipo=TransferenciaInterna.Tipo.MANUAL, 
                    bodega_origen=bodega_origen,
                    bodega_destino=bodega_destino,
                    usuario_solicita=request.user,
                    estado=TransferenciaInterna.Estado.SOLICITADA,
                    observaciones=f"Push Manual: {len(lotes_validos)} lotes."
                )

                # Ubicaciones Destino (Carrusel)
                ubicaciones = list(UbicacionFisica.objects.filter(
                    rack__zona__bodega=bodega_destino, es_activo=True
                ).order_by('codigo_celda'))
                
                if not ubicaciones: raise Exception("La bodega destino no tiene ubicaciones configuradas.")
                
                idx = 0
                total_ubis = len(ubicaciones)
                lotes_por_prod = defaultdict(list)
                
                for l in lotes_validos:
                    lotes_por_prod[l.producto].append(l)

                for prod, lista in lotes_por_prod.items():
                    cant_total = sum(x.cantidad_disponible for x in lista)
                    
                    det = DetalleTransferenciaInterna.objects.create(
                        transferencia=trf, producto=prod, cantidad_solicitada=cant_total
                    )
                    
                    for l_orig in lista:
                        DetalleTransferenciaLote.objects.create(
                            detalle=det,
                            stock_lote_origen=l_orig,
                            cantidad=l_orig.cantidad_disponible,
                            ubicacion_destino=ubicaciones[idx % total_ubis]
                        )
                        idx += 1

                messages.success(request, f" Transferencia {trf.codigo} creada correctamente.")
                return redirect('miapp:transferencias_consulta')

        except Exception as e:
            messages.error(request, f" No se pudo procesar: {str(e)}")

    ctx.update({
        'bodegas': bodegas, 'lotes': lotes_disponibles,
        'origen_seleccionado': int(origen_id) if origen_id else None,
        'titulo': "Transferencia Manual (Push)"
    })
    return render(request, "miapp/operaciones/transferencia_manual.html", ctx)


@login_required
def api_productos_por_bodega(request):
    """
    API AJAX: Retorna productos compatibles con las zonas de una bodega específica.
    """
    bodega_id = request.GET.get('bodega_id')
    if not bodega_id:
        return JsonResponse({'productos': []})

    try:
        # 1. Buscar tipos de almacenamiento de esa bodega
        tipos_validos = ZonaAlmacenamiento.objects.filter(
            bodega_id=bodega_id, 
            es_activo=True
        ).values_list('tipo_almacenamiento', flat=True).distinct()

        # 2. Filtrar productos
        productos = Producto.objects.filter(
            es_activo=True,
            tipo_almacenamiento__in=tipos_validos
        ).values(
            'id', 'nombre', 'codigo_sku', 'costo_compra', 
            'perfil_caducidad__requiere_caducidad'
        )

        # 3. Formatear para JSON
        data = []
        for p in productos:
            data.append({
                'id': p['id'],
                'text': f"{p['codigo_sku'] or 'S/C'} - {p['nombre']}", # Texto para Select2
                'costo': str(p['costo_compra']),
                'fefo': 'SI' if p['perfil_caducidad__requiere_caducidad'] else 'NO'
            })
        
        return JsonResponse({'productos': data})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
# ==============================================================================
#  AJUSTES DE INVENTARIO (MERMAS / PÉRDIDAS) - VERSIÓN ROBUSTA
# ==============================================================================
@login_required
@requiere_bodega_o_admin
def mov_ajustes(request):
    """
    AJUSTES DE INVENTARIO (CORRECCIÓN MATEMÁTICA TOTAL)
    Soluciona el error de integridad ajustando el 'stock_antes' para que la
    ecuación (Antes - Cantidad = Después) siempre sea válida.
    """
    ctx = _get_context_base(request)
    perfil = ctx['perfil']
    es_admin = ctx['es_admin']
    mi_bodega = perfil.bodega if perfil else None

    MOTIVOS = [
        ('ROBO', 'Robo / Hurto'),
        ('DAÑO_INTERNO', 'Daño Interno (Manejo)'),
        ('CADUCIDAD', 'Caducidad / Vencimiento'),
        ('MERMA_NATURAL', 'Merma Natural'),
        ('ERROR_INVENTARIO', 'Corrección de Conteo'),
        ('MUESTRA', 'Salida por Muestra/Marketing'),
    ]

    bodegas = Bodega.objects.filter(es_activo=True) if es_admin else [mi_bodega]

    if request.method == 'POST':
        try:
            with transaction.atomic():
                bodega_id = request.POST.get('bodega')
                motivo_codigo = request.POST.get('motivo')
                observacion_extra = request.POST.get('observacion', '')
                lotes_ids = request.POST.getlist('lote_id[]')
                cantidades = request.POST.getlist('cantidad[]')

                if not bodega_id or not motivo_codigo or not lotes_ids:
                    raise ValidationError("Datos incompletos.")

                if not es_admin and str(bodega_id) != str(mi_bodega.id):
                    raise ValidationError("Permiso denegado.")

                total_unidades = 0
                motivo_texto = dict(MOTIVOS).get(motivo_codigo, motivo_codigo)
                
                tm_ajuste, _ = TipoMovimiento.objects.get_or_create(
                    codigo=TipoMovimiento.CODIGO_AJUSTE_NEG,
                    defaults={'descripcion': 'Ajuste Negativo', 'es_salida': True, 'afecta_stock': True}
                )

                for i, lid in enumerate(lotes_ids):
                    try:
                        cant_baja = int(cantidades[i])
                    except: continue
                    if cant_baja <= 0: continue

                    # 1. Bloqueo de Lote
                    lote = StockLote.objects.select_for_update().get(pk=lid)
                    if lote.cantidad_disponible < cant_baja:
                        raise ValidationError(f"Lote {lote.lote}: Stock insuficiente en lote.")

                    # 2. Bloqueo de Inventario Global
                    inv, _ = InventarioProducto.objects.select_for_update().get_or_create(
                        producto=lote.producto, 
                        bodega_id=bodega_id,
                        defaults={'stock_actual': 0}
                    )

                    # === LA CORRECCIÓN MATEMÁTICA ===
                    # Si el global es menor a lo que vamos a restar, significa que está desincronizado.
                    # Primero LO ARREGLAMOS para que tenga stock suficiente.
                    if inv.stock_actual < cant_baja:
                        # "Inflamos" el stock global justo antes de la operación para que cuadre
                        inv.stock_actual = cant_baja
                        inv.save() # Guardamos este estado "arreglado"

                    # 3. Capturamos el estado "Antes" (Ahora ya es correcto, por ejemplo: 20)
                    stock_antes = inv.stock_actual

                    # 4. Realizamos la resta
                    lote.cantidad_disponible -= cant_baja
                    lote._auto_archivar_si_corresponde()
                    lote.save()

                    inv.stock_actual -= cant_baja
                    inv.fecha_ultimo_movimiento = timezone.now()
                    inv.save()

                    # 5. Registramos el movimiento
                    # Ahora la matemática es: 20 (antes) - 20 (cantidad) = 0 (después). ¡Perfecto!
                    MovimientoInventario.objects.create(
                        inventario=inv,
                        stock_lote=lote,
                        tipo_movimiento=tm_ajuste,
                        usuario=request.user,
                        bodega_origen_id=bodega_id,
                        cantidad=cant_baja,
                        stock_antes=stock_antes,
                        stock_despues=inv.stock_actual,
                        valor_unitario=lote.costo_compra_lote,
                        valor_total=cant_baja * lote.costo_compra_lote,
                        motivo=f"AJUSTE [{motivo_texto}]: {observacion_extra}"
                    )
                    total_unidades += cant_baja

            messages.success(request, f"Ajuste exitoso. Se dieron de baja {total_unidades} unidades.")
            return redirect('miapp:mov_ajustes')

        except Exception as e:
            messages.error(request, f"Error al procesar: {str(e)}")

    ctx.update({
        'titulo': "Gestión de Mermas y Pérdidas",
        'bodegas': bodegas,
        'motivos': MOTIVOS,
        'es_admin': es_admin,
        'mi_bodega': mi_bodega
    })
    return render(request, "miapp/operaciones/ajuste_form.html", ctx)


@login_required
def api_lotes_por_producto(request):
    bodega_id = request.GET.get('bodega_id')
    producto_id = request.GET.get('producto_id')
    
    if not bodega_id or not producto_id:
        return JsonResponse({'lotes': []})

    # CORRECCIÓN: Quitamos 'archivado=False' y 'estado_lote__es_vendible=True'
    # Queremos ver TODO lo que ocupe espacio físico (stock > 0), incluso si está vencido.
    lotes = StockLote.objects.filter(
        producto_id=producto_id,
        ubicacion__rack__zona__bodega_id=bodega_id,
        cantidad_disponible__gt=0  # Única condición física real
    ).select_related('ubicacion', 'estado_lote').order_by('fecha_caducidad')

    data = []
    hoy = timezone.now().date()

    for l in lotes:
        # Calculamos estado visual para el frontend
        es_vencido = l.fecha_caducidad and l.fecha_caducidad <= hoy
        estado_texto = "VENCIDO" if es_vencido else l.estado_lote.descripcion

        data.append({
            'id': l.id,
            'lote': l.lote,
            'ubicacion': l.ubicacion.codigo_celda,
            'vencimiento': l.fecha_caducidad.strftime('%Y-%m-%d') if l.fecha_caducidad else 'N/A',
            'stock': l.cantidad_disponible,
            'estado': estado_texto, # Para mostrar en el select si deseas
            'es_vencido': es_vencido # Flag útil para pintar de rojo en el frontend
        })
    
    return JsonResponse({'lotes': data})

from django.db import transaction
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from decimal import Decimal
import json
# ==============================================================================
# 6. CREACIÓN RÁPIDA DE PRODUCTOS (AJAX)
# ==============================================================================
@login_required
@require_POST
def producto_quick_create(request):
    """
    CREACIÓN RÁPIDA INTELIGENTE:
    1. Valida datos obligatorios.
    2. Valida compatibilidad logística (¿La bodega soporta este tipo de producto?).
    3. Configura estrategia de salida (FIFO/FEFO) alineada al modelo.
    """
    try:
        # 1. Recolección de Datos
        nombre = request.POST.get('nombre', '').strip().title()
        
        # Diccionario de campos requeridos (Nombre en form -> Nombre legible)
        campos_requeridos = {
            'categoria_id': 'Categoría',
            'marca_id': 'Marca',
            'tipo_almacenamiento_id': 'Tipo de Almacenamiento',
            'clase_producto_id': 'Clase de Producto',
            'impuesto_id': 'Impuesto',
            'estrategia_salida': 'Estrategia de Salida'
        }

        errores = []
        if not nombre: errores.append("Nombre del producto")
        
        datos = {}
        for key, label in campos_requeridos.items():
            val = request.POST.get(key)
            if not val:
                errores.append(label)
            else:
                datos[key] = val

        if errores:
            return JsonResponse({'success': False, 'error': f"Faltan datos obligatorios: {', '.join(errores)}."})

        # 2. Validación de Precios
        try:
            costo = Decimal(str(request.POST.get('costo', 0)))
            precio = Decimal(str(request.POST.get('precio', 0)))
            if costo < 0 or precio < 0: raise ValueError
        except:
            return JsonResponse({'success': False, 'error': 'El costo y precio deben ser números positivos.'})

        # 3. VALIDACIÓN DE COMPATIBILIDAD LOGÍSTICA (GATEKEEPER)
        # Verificamos si la bodega actual tiene zonas para este tipo de almacenamiento.
        bodega_id = request.POST.get('bodega_id_contexto')
        tipo_alm_id = datos['tipo_almacenamiento_id']

        if bodega_id:
            capacidad_existente = ZonaAlmacenamiento.objects.filter(
                bodega_id=bodega_id,
                tipo_almacenamiento_id=tipo_alm_id,
                es_activo=True
            ).exists()

            if not capacidad_existente:
                # Obtenemos nombres para el mensaje de error amigable
                b_nombre = Bodega.objects.filter(pk=bodega_id).values_list('nombre', flat=True).first()
                t_nombre = TipoAlmacenamiento.objects.filter(pk=tipo_alm_id).values_list('descripcion', flat=True).first()
                return JsonResponse({
                    'success': False, 
                    'error': f"INCOMPATIBILIDAD: La bodega '{b_nombre}' no tiene zonas habilitadas para '{t_nombre}'. No puede recibir este producto aquí."
                })

        # 4. Lógica de Negocio (FEFO vs Perfil)
        estrategia = datos['estrategia_salida']
        perfil_id = request.POST.get('perfil_caducidad_id')
        
        if estrategia == 'FEFO' and not perfil_id:
            return JsonResponse({'success': False, 'error': "Para estrategia FEFO es obligatorio seleccionar un Perfil de Caducidad."})

        # 5. Transacción de Guardado
        with transaction.atomic():
            nuevo_prod = Producto(
                nombre=nombre,
                costo_compra=costo,
                precio_venta=precio,
                
                # Relaciones
                categoria_id=datos['categoria_id'],
                marca_id=datos['marca_id'],
                tipo_almacenamiento_id=datos['tipo_almacenamiento_id'],
                clase_producto_id=datos['clase_producto_id'],
                impuesto_id=datos['impuesto_id'],
                
                # Configuración Logística
                estrategia_salida=estrategia,
                perfil_caducidad_id=perfil_id if perfil_id else None,
                
                es_activo=True,
                es_publico=False,
                notas_manejo="Creado vía Recepción Rápida"
            )
            
            nuevo_prod.full_clean() 
            nuevo_prod.save() 

            # Guardar Imagen (si existe)
            imagen_archivo = request.FILES.get('imagen')
            if imagen_archivo:
                ImagenProducto.objects.create(
                    producto=nuevo_prod,
                    imagen=imagen_archivo,
                    orden=0 # Se marca como principal automáticamente por el modelo
                )

        # 6. Respuesta Exitosa
        # Calculamos si el frontend debe pedir fecha obligatoria
        requiere_fecha = False
        if nuevo_prod.perfil_caducidad and nuevo_prod.perfil_caducidad.requiere_caducidad:
            requiere_fecha = True

        return JsonResponse({
            'success': True,
            'producto': {
                'id': nuevo_prod.id,
                'text': f"{nuevo_prod.codigo_sku} - {nuevo_prod.nombre}",
                'costo': str(nuevo_prod.costo_compra),
                'fefo': 'SI' if requiere_fecha else 'NO'
            }
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': f"Error técnico: {str(e)}"})