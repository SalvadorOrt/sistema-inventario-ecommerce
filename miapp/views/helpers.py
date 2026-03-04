# miapp/views/helpers.py
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from ..models import PerfilUsuario

def _get_perfil_rol(request):
    """
    Obtiene el perfil y el rol del usuario actual buscando en las 
    posibles relaciones OneToOne.
    """
    perfil = getattr(request.user, "perfil", None) or getattr(request.user, "perfilusuario", None)
    rol = getattr(perfil, "rol_negocio", None)
    return perfil, rol

# ==========================================================
# DECORADORES DE ROL
# ==========================================================

def requiere_rol(*roles_permitidos):
    # ... (tu código existente de requiere_rol) ...
    def deco(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            _, rol = _get_perfil_rol(request)
            if rol not in roles_permitidos:
                messages.error(request, "Acceso denegado. No tiene los permisos suficientes.")
                return redirect("miapp:inicio")
            return view_func(request, *args, **kwargs)
        return _wrapped
    return deco

def requiere_admin_negocio(view_func):
    """Acceso exclusivo para administradores del sistema."""
    return requiere_rol(PerfilUsuario.RolNegocio.ADMIN_SISTEMA)(view_func)

# --- AGREGA ESTO NUEVO ---
def requiere_ventas_o_admin(view_func):
    """Permite acceso a Vendedores y Administradores (Cartera de Clientes)."""
    return requiere_rol(
        PerfilUsuario.RolNegocio.ADMIN_SISTEMA,
        PerfilUsuario.RolNegocio.VENDEDOR
    )(view_func)
def requiere_bodega_o_admin(view_func):
    """Acceso para Operadores Logísticos y Administradores (Movimientos físicos)."""
    return requiere_rol(
        PerfilUsuario.RolNegocio.ADMIN_SISTEMA,
        PerfilUsuario.RolNegocio.OPERADOR_OPERACIONES
    )(view_func)
# ==========================================================
# MENÚS (Estructura Jerárquica Actualizada)
# ==========================================================

# Catálogos maestros (Crear, Editar y Consultar)
MENU_GESTION_CATALOGO = [
    # --- Catálogos de Entidades ---
    {"nombre": "Gestión de Productos", "url": "miapp:productos_gestion", "grupo": "Catálogos"},
    {"nombre": "Categorías", "url": "miapp:categorias_gestion", "grupo": "Catálogos"},
    {"nombre": "Marcas", "url": "miapp:marcas_gestion", "grupo": "Catálogos"},
    {"nombre": "Proveedores", "url": "miapp:proveedores_gestion", "grupo": "Catálogos"},
    {"nombre": "Clientes (Cartera)", "url": "miapp:clientes_gestion", "grupo": "Catálogos"},
    
    # --- Infraestructura Logística ---
    {"nombre": "Bodegas (Sedes)", "url": "miapp:bodegas_gestion", "grupo": "Infraestructura"},
    {"nombre": "Zonas", "url": "miapp:zonas_gestion", "grupo": "Infraestructura"},
    {"nombre": "Racks", "url": "miapp:racks_gestion", "grupo": "Infraestructura"},
    {"nombre": "Mapa Distribución", "url": "miapp:mapa_distribucion", "grupo": "Infraestructura"},
    
    # --- Configuración ---
    {"nombre": "Impuestos", "url": "miapp:impuestos_gestion", "grupo": "Configuración"},
    {"nombre": "Tipos Almacenamiento", "url": "miapp:tipos_almacenamiento_gestion", "grupo": "Configuración"},
    {"nombre": "Tipos Identificación", "url": "miapp:tipos_identidad_gestion", "grupo": "Configuración"},
    {"nombre": "Clases Producto", "url": "miapp:clases_producto_gestion", "grupo": "Configuración"},
    {"nombre": "Perfiles Caducidad", "url": "miapp:perfiles_caducidad_gestion", "grupo": "Configuración"},
    {"nombre": "Estados Lote", "url": "miapp:estados_lote_gestion", "grupo": "Configuración"},
    {"nombre": "Estados Pedido", "url": "miapp:estados_pedido_gestion", "grupo": "Configuración"},
    {"nombre": "Tipos Movimiento", "url": "miapp:tipos_movimiento_gestion", "grupo": "Configuración"},
    {"nombre": "Países", "url": "miapp:paises_gestion", "grupo": "Configuración"},
]

MENU_ADMIN = [
    {"nombre": "Dashboard", "url": "miapp:inicio", "grupo": "Panel"},

    # Consultas Operativas Globales
    {"nombre": "Inventario Global", "url": "miapp:inventario_global_consulta", "grupo": "Consultas"},
    {"nombre": "Mapa Multi-Bodega", "url":"miapp:mapa_distribucion", "grupo": "Consultas"},
    {"nombre": "Kardex General", "url": "miapp:kardex_consulta", "grupo": "Consultas"},
    {"nombre": "Transferencias", "url": "miapp:transferencias_consulta", "grupo": "Consultas"},
    {"nombre": "Pedidos Ventas", "url": "miapp:pedidos_consulta", "grupo": "Consultas"},
    {"nombre": "Historial Compras", "url": "miapp:compras_list", "grupo": "Consultas"},

    # Operación
    {"nombre": "Recepción Mercancía", "url": "miapp:mov_entrada", "grupo": "Operación"},
    {"nombre": "Despacho Pedidos", "url": "miapp:mov_salida", "grupo": "Operación"},
    
    # Transferencias (Acceso directo para admin)
    {"nombre": "Solicitar Stock (Pull)", "url": "miapp:transferencia_solicitar", "grupo": "Operación"},
    {"nombre": "Mover Lotes (Push)", "url": "miapp:transferencia_manual", "grupo": "Operación"},

    # Seguridad y Reportes
   
    {"nombre": "Perfiles", "url": "miapp:perfiles_consulta", "grupo": "Administración"},
    {"nombre": "Reportes", "url": "miapp:reportes_home", "grupo": "Administración"},
] + MENU_GESTION_CATALOGO

MENU_BODEGA = [
    # 1. PANEL PRINCIPAL
    {"nombre": "Dashboard", "url": "miapp:inicio", "grupo": "Panel"},

    # 2. CATÁLOGOS OPERATIVOS (El 'Checkpoint' del Bodeguero)
    # Acceso total a Crear/Buscar para no detener la operación si llega algo nuevo.
    {"nombre": "Productos", "url": "miapp:productos_gestion", "grupo": "Catálogos"},
    {"nombre": "Proveedores", "url": "miapp:proveedores_gestion", "grupo": "Catálogos"},
    {"nombre": "Marcas", "url": "miapp:marcas_gestion", "grupo": "Catálogos"},
    {"nombre": "Categorías", "url": "miapp:categorias_gestion", "grupo": "Catálogos"},

    # 3. CONSULTAS (Visibilidad limitada a su bodega)
    {"nombre": "Mi Inventario", "url": "miapp:inventario_global_consulta", "grupo": "Consultas"}, 
    {"nombre": "Mapa de Bodega", "url": "miapp:mapa_distribucion", "grupo": "Consultas"},
    {"nombre": "Historial Transferencias", "url": "miapp:transferencias_consulta", "grupo": "Consultas"},
    {"nombre": "Mis Recepciones", "url": "miapp:compras_list", "grupo": "Consultas"},
    
    # 4. OPERACIÓN DIARIA (Flujo de entrada y salida)
    #{"nombre": "Recibir Compra", "url": "miapp:mov_entrada", "grupo": "Operación"},
    {"nombre": "Despachar Pedido", "url": "miapp:mov_salida", "grupo": "Operación"},
    
    # 5. GESTIÓN DE TRANSFERENCIAS INTERNAS
    {"nombre": "Pedir Stock (Pull)", "url": "miapp:transferencia_solicitar", "grupo": "Operación"},
    {"nombre": "Enviar Stock (Push)", "url": "miapp:transferencia_manual", "grupo": "Operación"},
]

MENU_VENDEDOR = [
    {"nombre": "Dashboard", "url": "miapp:inicio", "grupo": "Panel"},

    # Consultas
    {"nombre": "Catálogo Productos", "url": "miapp:productos_gestion", "grupo": "Consultas"},
    {"nombre": "Stock Disponible", "url": "miapp:inventario_global_consulta", "grupo": "Consultas"},
    {"nombre": "Clientes", "url": "miapp:clientes_gestion", "grupo": "Consultas"},

    # Ventas
    {"nombre": "Nuevo Pedido", "url": "miapp:pedido_nuevo", "grupo": "Ventas"},
    {"nombre": "Mis Ventas", "url": "miapp:pedidos_consulta", "grupo": "Ventas"}, # Apunta a consulta filtrada
    {"nombre": "Nuevo Cliente", "url": "miapp:cliente_crear", "grupo": "Ventas"},

    # Abastecimiento (Alertas)
    # {"nombre": "Solicitar Stock", "url": "miapp:transferencia_solicitar", "grupo": "Abastecimiento"},
]

# Diccionario maestro de acceso por rol
OPERACIONES_POR_ROL = {
    PerfilUsuario.RolNegocio.ADMIN_SISTEMA: MENU_ADMIN,
    PerfilUsuario.RolNegocio.OPERADOR_OPERACIONES: MENU_BODEGA,
    PerfilUsuario.RolNegocio.VENDEDOR: MENU_VENDEDOR,
}

# ==========================================================
# FUNCIONES DE CONTEXTO
# ==========================================================

def _get_context_base(request):
    """
    Retorna el contexto básico compartido por todas las vistas protegidas.
    """
    perfil, rol = _get_perfil_rol(request)
    operaciones = OPERACIONES_POR_ROL.get(rol, []) if rol else []
    return {
        "perfil": perfil,
        "rol": rol,
        "operaciones": operaciones,
        "es_admin": rol == PerfilUsuario.RolNegocio.ADMIN_SISTEMA,
        "es_bodega": rol == PerfilUsuario.RolNegocio.OPERADOR_OPERACIONES,
        "es_vendedor": rol == PerfilUsuario.RolNegocio.VENDEDOR,
    }