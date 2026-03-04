from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import F, Q, Sum, Count
from django.db.models.functions import TruncMonth, TruncDay
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.cache import never_cache

from .helpers import _get_context_base, _get_perfil_rol
from ..models import (
    InventarioProducto, StockLote, Pedido,
    TransferenciaInterna, PerfilUsuario, Bodega,
    MovimientoInventario, UbicacionFisica, DetallePedido
)

User = get_user_model()

# ==========================================================
# VISTAS DE ACCESO
# ==========================================================
@never_cache
def login_view(request):
    if request.user.is_authenticated:
        return redirect("miapp:inicio")
    if request.method == "POST":
        correo = (request.POST.get("correo") or "").strip()
        password = request.POST.get("password") or ""
        user_obj = User.objects.filter(email__iexact=correo).first()
        username_auth = user_obj.username if user_obj else correo
        user = authenticate(request, username=username_auth, password=password)

        if user and user.is_active:
            # FIX temporal para obtener perfil antes de login formal
            _old_user = getattr(request, "user", None)
            request.user = user
            perfil, rol = _get_perfil_rol(request)
            request.user = _old_user

            if not perfil:
                messages.error(request, "Usuario sin perfil de negocio asignado.")
                return render(request, "miapp/login.html")
            if rol == PerfilUsuario.RolNegocio.OPERADOR_OPERACIONES and not perfil.bodega_id:
                messages.error(request, "Operador sin bodega asignada.")
                return render(request, "miapp/login.html")
            
            login(request, user)
            return redirect("miapp:inicio")
        messages.error(request, "Credenciales inválidas.")
    return render(request, "miapp/login.html")

def logout_view(request):
    logout(request)
    messages.info(request, "Sesión cerrada correctamente.")
    return redirect("miapp:login")

# ==========================================================
# DASHBOARD ESTRATÉGICO OPTIMIZADO
# ==========================================================

@never_cache
@login_required
def inicio(request):
    ctx = _get_context_base(request)
    perfil, rol = _get_perfil_rol(request)

    hoy = timezone.localdate()
    inicio_mes = hoy.replace(day=1)
    prox_30 = hoy + timedelta(days=30)
    ult_7 = hoy - timedelta(days=6)

    # --- FILTRO DE BODEGA ---
    bodega_id = request.GET.get("bodega")
    bodega_nombre = "Global"
    bodega_obj = None

    if rol == PerfilUsuario.RolNegocio.ADMIN_SISTEMA:
        if bodega_id:
            bodega_obj = Bodega.objects.filter(id=bodega_id).first()
            if bodega_obj: 
                bodega_nombre = bodega_obj.nombre
        else:
            bodega_id = None
    else:
        bodega_obj = perfil.bodega if perfil else None
        bodega_id = bodega_obj.id if bodega_obj else None
        bodega_nombre = bodega_obj.nombre if bodega_obj else "No asignada"

    # --- QUERYSETS BASE ---
    inv_qs = InventarioProducto.objects.select_related("producto", "bodega")
    lotes_qs = StockLote.objects.select_related(
        "producto", "ubicacion__rack__zona__bodega", "estado_lote"
    ).filter(archivado=False)
    pedidos_qs = Pedido.objects.select_related("cliente", "estado_pedido", "usuario")
    transf_qs = TransferenciaInterna.objects.select_related("bodega_origen", "bodega_destino", "usuario_solicita")
    mov_qs = MovimientoInventario.objects.select_related("tipo_movimiento", "inventario__bodega")

    # Aplicar filtros de jerarquía física
    if bodega_id:
        inv_qs = inv_qs.filter(bodega_id=bodega_id)
        lotes_qs = lotes_qs.filter(ubicacion__rack__zona__bodega_id=bodega_id)
        mov_qs = mov_qs.filter(inventario__bodega_id=bodega_id)
        transf_qs = transf_qs.filter(Q(bodega_origen_id=bodega_id) | Q(bodega_destino_id=bodega_id))
        pedidos_qs = pedidos_qs.filter(movimientos_inventario__inventario__bodega_id=bodega_id).distinct()

    # --- HELPERS ---
    def _sum(qs, field): return qs.aggregate(t=Sum(field))["t"] or 0
    def _count(qs): return qs.count() if qs else 0
    def _wrap_acc(*items): return [{"nombre": n, "url": u, "color": (c or "primary")} for n, u, c in items if u]

    # Alertas comunes
    qs_criticos = inv_qs.filter(stock_actual__lte=F("stock_minimo"))
    qs_prox_vencer = lotes_qs.filter(
        fecha_caducidad__isnull=False,
        fecha_caducidad__gte=hoy,
        fecha_caducidad__lte=prox_30,
        cantidad_disponible__gt=0
    )

    tarjetas, graficos = [], {}
    paneles = {"criticos": [], "caducidad": [], "transferencias": [], "pedidos": []}

    # =======================================================
    # 1) ADMIN_SISTEMA
    # =======================================================
    if rol == PerfilUsuario.RolNegocio.ADMIN_SISTEMA:
        
        # --- CÁLCULO DE KPI ---
        if bodega_obj:
            stats_movs = MovimientoInventario.objects.filter(
                inventario__bodega=bodega_obj,
                pedido__isnull=False,
                tipo_movimiento__es_salida=True
            ).aggregate(
                ingresos=Sum('valor_total'),
                utilidad=Sum('pedido__ganancia_total')
            )
            ventas_display = stats_movs['ingresos'] or Decimal('0.00')
            ganancia_display = _sum(pedidos_qs.filter(ganancia_total__gt=0), "ganancia_total") 
        else:
            ganancia_display = _sum(pedidos_qs.filter(ganancia_total__gt=0), "ganancia_total")
            ventas_display = _sum(pedidos_qs, "total")

        # --- CORRECCIÓN INTELIGENTE DE PÉRDIDAS MES ---
        # Lógica: Sumamos TODO lo que sea Salida, EXCEPTO lo que es Venta o Traslado.
        # Esto atrapa automáticamente "AJUSTE_NEGATIVO", "ROBO", "MERMA", "CADUCIDAD".
        codigos_no_perdida = ['DESPACHO_PEDIDO', 'TRANSFERENCIA_SALIDA', 'REUBICACION']
        
        p_mes = _sum(
            mov_qs.filter(
                fecha__date__gte=inicio_mes,
                tipo_movimiento__es_salida=True  # 1. Filtro: Es salida real
            ).exclude(
                tipo_movimiento__codigo__in=codigos_no_perdida # 2. Filtro: No es venta ni traslado
            ),
            "valor_total"
        )

        tarjetas = [
            {"titulo": f"Ganancia {bodega_nombre}", "valor": f"${ganancia_display:,.2f}", "color": "success"},
            {"titulo": f"Ventas {bodega_nombre}", "valor": f"${ventas_display:,.2f}", "color": "primary"},
            {"titulo": "Pérdidas/Mermas Mes", "valor": f"${p_mes:,.2f}", "color": "danger"},
        ]

        paneles["criticos"] = qs_criticos.order_by("stock_actual")[:10]
        paneles["caducidad"] = qs_prox_vencer.order_by("fecha_caducidad")[:10]
        paneles["transferencias"] = transf_qs.exclude(estado__in=["RECIBIDA", "CANCELADA"]).order_by("-fecha_creacion")[:10]

        acciones_rapidas = _wrap_acc(
            ("Transferencia", "miapp:transferencia_solicitar", "primary"),
            ("Registrar ajuste/merma", "miapp:mov_ajustes", "danger"),
            ("Inventario global", "miapp:inventario_global_consulta", "primary"),
            ("Mapa multi-bodega", "miapp:mapa_distribucion", "info"),
            ("Reportes Financieros", "miapp:reportes_home", "success"),
             ("Gestión de productos", "miapp:productos_gestion", "dark"),
        )

    # =======================================================
    # 2) OPERADOR_OPERACIONES (BODEGA)
    # =======================================================
    elif rol == PerfilUsuario.RolNegocio.OPERADOR_OPERACIONES:
        tr_recibir = transf_qs.filter(bodega_destino_id=bodega_id).exclude(estado__in=["RECIBIDA", "CANCELADA"])
        tr_despachar = transf_qs.filter(bodega_origen_id=bodega_id).exclude(estado__in=["RECIBIDA", "CANCELADA"])

        total_ubic = UbicacionFisica.objects.filter(rack__zona__bodega_id=bodega_id).count()
        ocupadas = UbicacionFisica.objects.filter(
            rack__zona__bodega_id=bodega_id,
            lotes__archivado=False,
            lotes__cantidad_disponible__gt=0
        ).distinct().count()

        tarjetas = [
            {"titulo": "Por Recibir", "valor": _count(tr_recibir), "color": "primary"},
            {"titulo": "Por Despachar", "valor": _count(tr_despachar), "color": "info"},
            {"titulo": "Ocupación Bodega", "valor": f"{ocupadas} / {total_ubic}", "color": "warning"},
            {"titulo": "Celdas Libres", "valor": max(0, total_ubic - ocupadas), "color": "success"},
        ]

        paneles["transferencias"] = (tr_recibir | tr_despachar).order_by("fecha_creacion")[:10]
        paneles["pedidos"] = [] 
        paneles["caducidad"] = qs_prox_vencer.order_by("fecha_caducidad")[:8]

        acciones_rapidas = _wrap_acc(
            ("Nueva recepción", "miapp:mov_entrada", "primary"),
            ("Nuevo despacho", "miapp:mov_salida", "info"),
            ("Ver mapa de celdas", "miapp:mapa_distribucion", "success"),
            ("Mi inventario", "miapp:inventario_global_consulta", "dark"),
        )

    # =======================================================
    # 3) VENDEDOR (VENTAS)
    # =======================================================
    elif rol == PerfilUsuario.RolNegocio.VENDEDOR:
        mis_pedidos = pedidos_qs.filter(usuario=request.user)
        v_hoy = _sum(mis_pedidos.filter(fecha_creacion__date=hoy), "total")
        g_hoy = _sum(mis_pedidos.filter(fecha_creacion__date=hoy), "ganancia_total")
        abiertos = mis_pedidos.exclude(estado_pedido__codigo__in=["ENTREGADO", "CANCELADO", "FINALIZADO"])

        tarjetas = [
            {"titulo": "Mis Ventas Hoy", "valor": f"${v_hoy:,.2f}", "color": "success"},
            {"titulo": "Mi Ganancia Hoy", "valor": f"${max(0, g_hoy):,.2f}", "color": "primary"},
            {"titulo": "Pedidos Abiertos", "valor": _count(abiertos), "color": "info"},
        ]

        paneles["pedidos"] = mis_pedidos.order_by("-fecha_creacion")[:8]
        acciones_rapidas = _wrap_acc(
            ("Crear pedido", "miapp:pedido_nuevo", "primary"),
            ("Nuevo cliente", "miapp:cliente_crear", "success"),
            ("Consultar stock", "miapp:inventario_global_consulta", "info"),
        )
    
    elif rol == 'CLIENTE' or rol == 'USUARIO_WEB':
        return redirect('tienda:catalogo')

    # --- GRÁFICOS ---
    try:
        v7 = pedidos_qs.filter(fecha_creacion__date__gte=ult_7).annotate(
            dia=TruncDay("fecha_creacion")
        ).values("dia").annotate(t=Sum("total")).order_by("dia")
        
        graficos["labels"] = [v["dia"].strftime("%d/%m") for v in v7]
        graficos["data"] = [float(v["t"]) for v in v7]
    except:
        pass

    ctx.update({
        "tarjetas": tarjetas,
        "paneles": paneles,
        "acciones_rapidas": acciones_rapidas,
        "graficos": graficos,
        "bodega_nombre": bodega_nombre,
        "hoy": hoy,
        "bodegas_lista": Bodega.objects.filter(es_activo=True) if rol == PerfilUsuario.RolNegocio.ADMIN_SISTEMA else [],
        "bodega_actual": str(bodega_id or ""),
    })
    return render(request, "miapp/inicio.html", ctx)