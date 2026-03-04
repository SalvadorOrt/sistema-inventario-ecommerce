from django.urls import path
from miapp.views import (
    auth_views, 
    catalogo_views, 
    infraestructura_views, 
    configuracion_views, 
    inventario_views,
    consultas_views,
    operaciones_views, 
    admin_views
)

app_name = 'miapp'

urlpatterns = [
    # ==========================================
    # 1. AUTENTICACIÓN Y HOME
    # ==========================================
    path('', auth_views.login_view, name='login'),
    path('inicio/', auth_views.inicio, name='inicio'),
    path('logout/', auth_views.logout_view, name='logout'),

    # ==========================================
    # 2. CATÁLOGOS (Maestros de Datos)
    # ==========================================
    # Productos
    path('catalogo/productos/', catalogo_views.productos_gestion, name='productos_gestion'),
    path('catalogo/productos/nuevo/', catalogo_views.producto_crear, name='producto_crear'),
    path('catalogo/productos/editar/<int:pk>/', catalogo_views.producto_editar, name='productos_editar'),
    path('catalogo/productos/detalle/<int:id>/', catalogo_views.producto_detalle, name='producto_detalle'),

    # Categorías
    path('catalogo/categorias/', catalogo_views.categorias_gestion, name='categorias_gestion'),
    path('catalogo/categorias/nuevo/', catalogo_views.categoria_crear, name='categoria_crear'),
    path('catalogo/categorias/editar/<int:pk>/', catalogo_views.categoria_editar, name='categoria_editar'),
    path('catalogo/categorias/detalle/<int:pk>/', catalogo_views.categoria_detalle, name='categoria_detalle'),

    # Marcas
    path('catalogo/marcas/', catalogo_views.marcas_gestion, name='marcas_gestion'),
    path('catalogo/marcas/nuevo/', catalogo_views.marca_crear, name='marca_crear'),
    path('catalogo/marcas/editar/<int:pk>/', catalogo_views.marca_editar, name='marca_editar'),
    path('catalogo/marcas/detalle/<int:pk>/', catalogo_views.marca_detalle, name='marca_detalle'),

    # Proveedores
    path('catalogo/proveedores/', catalogo_views.proveedores_gestion, name='proveedores_gestion'),
    path('catalogo/proveedores/nuevo/', catalogo_views.proveedor_crear, name='proveedor_crear'),
    path('catalogo/proveedores/editar/<int:pk>/', catalogo_views.proveedor_editar, name='proveedor_editar'),
    path('catalogo/proveedores/detalle/<int:pk>/', catalogo_views.proveedor_detalle, name='proveedor_detalle'),

    # Clientes
    path('catalogo/clientes/', catalogo_views.clientes_gestion, name='clientes_gestion'),
    path('catalogo/clientes/nuevo/', catalogo_views.cliente_crear, name='cliente_crear'),
    path('catalogo/clientes/editar/<int:pk>/', catalogo_views.cliente_editar, name='cliente_editar'),
    path('catalogo/clientes/detalle/<int:pk>/', catalogo_views.cliente_detalle, name='cliente_detalle'),

    # ==========================================
    # 3. INFRAESTRUCTURA (Almacenamiento)
    # ==========================================
    # Bodegas
    path('infraestructura/bodegas/', infraestructura_views.bodegas_gestion, name='bodegas_gestion'),
    path('infraestructura/bodegas/nuevo/', infraestructura_views.bodega_crear, name='bodega_crear'),
    path('infraestructura/bodegas/<int:pk>/editar/', infraestructura_views.bodega_editar, name='bodega_editar'),
    path('infraestructura/bodegas/<int:pk>/detalle/', infraestructura_views.bodega_detalle, name='bodega_detalle'),

    # Zonas
    path('infraestructura/zonas/', infraestructura_views.zonas_gestion, name='zonas_gestion'),
    path('infraestructura/zonas/nuevo/', infraestructura_views.zona_crear, name='zona_crear'),
    path('infraestructura/zonas/<int:pk>/editar/', infraestructura_views.zona_editar, name='zona_editar'),
    path('infraestructura/zonas/<int:pk>/detalle/', infraestructura_views.zona_detalle, name='zona_detalle'),

    # Racks y Niveles
    path('infraestructura/racks/', infraestructura_views.racks_gestion, name='racks_gestion'),
    path('infraestructura/racks/nuevo/', infraestructura_views.rack_crear, name='rack_crear'),
    path('infraestructura/racks/<int:pk>/editar/', infraestructura_views.rack_editar, name='rack_editar'),
    path('infraestructura/racks/<int:pk>/detalle/', infraestructura_views.rack_detalle, name='rack_detalle'),
    path('infraestructura/racks/<int:rack_id>/niveles/add/', infraestructura_views.nivel_añadir, name='nivel_anadir'),
    path('infraestructura/niveles/<int:pk>/eliminar/', infraestructura_views.nivel_eliminar, name='nivel_eliminar'),
    
    # Visualización
    path('infraestructura/mapa/', infraestructura_views.mapa_distribucion, name='mapa_distribucion'),

    # ==========================================
    # 4. CONFIGURACIÓN DEL SISTEMA
    # ==========================================
    path('configuracion/impuestos/', configuracion_views.impuestos_list, name='impuestos_gestion'),
    path('configuracion/impuestos/crear/', configuracion_views.impuesto_crear, name='impuesto_crear'),
    path('configuracion/impuestos/editar/<int:pk>/', configuracion_views.impuesto_editar, name='impuesto_editar'),

    path('configuracion/tipos-almacenamiento/', configuracion_views.tipos_almacenamiento_list, name='tipos_almacenamiento_gestion'),
    path('configuracion/tipos-almacenamiento/crear/', configuracion_views.tipo_almacenamiento_crear, name='tipo_almacenamiento_crear'),
    
    path('configuracion/tipos-identificacion/', configuracion_views.tipos_identificacion_list, name='tipos_identidad_gestion'),
    path('configuracion/tipos-identificacion/crear/', configuracion_views.tipo_identificacion_crear, name='tipo_identificacion_crear'),

    path('configuracion/clases-producto/', configuracion_views.clases_producto_list, name='clases_producto_gestion'),
    path('configuracion/clases-producto/crear/', configuracion_views.clase_producto_crear, name='clase_producto_crear'),

    path('configuracion/perfiles-caducidad/', configuracion_views.perfiles_caducidad_list, name='perfiles_caducidad_gestion'),
    path('configuracion/perfiles-caducidad/crear/', configuracion_views.perfil_caducidad_crear, name='perfil_caducidad_crear'),

    path('configuracion/estados-lote/', configuracion_views.estados_lote_list, name='estados_lote_gestion'),
    path('configuracion/estados-lote/crear/', configuracion_views.estado_lote_crear, name='estado_lote_crear'),

    path('configuracion/estados-pedido/', configuracion_views.estados_pedido_list, name='estados_pedido_gestion'),
    path('configuracion/estados-pedido/crear/', configuracion_views.estado_pedido_crear, name='estado_pedido_crear'),

    path('configuracion/tipos-movimiento/', configuracion_views.tipos_movimiento_list, name='tipos_movimiento_gestion'),
    path('configuracion/tipos-movimiento/crear/', configuracion_views.tipo_movimiento_crear, name='tipo_movimiento_crear'),

    path('configuracion/paises/', configuracion_views.paises_list, name='paises_gestion'),
    path('configuracion/paises/crear/', configuracion_views.pais_crear, name='pais_crear'),

    # ==========================================
    # 5. INVENTARIO Y CONSULTAS (Reportes)
    # ==========================================
    path('inventario/global/', inventario_views.inventario_global_list, name='inventario_global_consulta'),
    path('inventario/lote/<int:pk>/', inventario_views.lote_detail, name='lote_detail'),
    path('inventario/lote/<int:pk>/cambiar-estado/', inventario_views.lote_cambiar_estado, name='lote_cambiar_estado'),
    
    path('consultas/kardex/', consultas_views.kardex_consulta, name='kardex_consulta'),
    path('consultas/kardex/detalle/<int:pk>/', consultas_views.kardex_detalle, name='kardex_detalle'),
    
    path('consultas/transferencias/', consultas_views.transferencias_consulta, name='transferencias_consulta'),
    path('consultas/transferencias/detalle/<int:pk>/', consultas_views.transferencia_detalle, name='transferencia_detalle'),
    
    path('consultas/pedidos/', consultas_views.pedidos_consulta, name='pedidos_consulta'),
    path('consultas/pedidos/detalle/<int:pk>/', consultas_views.pedido_detalle, name='pedido_detalle'),
    
    path('consultas/compras/', consultas_views.compras_list, name='compras_list'),
    path('consultas/compras/<int:pk>/', consultas_views.compra_detail, name='compra_detail'),

    # ==========================================
    # 6. OPERACIONES (Entradas, Salidas y Stock)
    # ==========================================
    # Compras y Ventas
    path('operacion/recepcion/', operaciones_views.mov_entrada, name='mov_entrada'),
    path('operacion/salida/', operaciones_views.mov_salida, name='mov_salida'),         
    path('operacion/pedido-nuevo/', operaciones_views.pedido_create, name='pedido_nuevo'), 

    # Transferencias Logísticas
    path('operaciones/transferencias/solicitar/', operaciones_views.transferencia_solicitar, name='transferencia_solicitar'),
    path('operaciones/transferencias/<int:trf_id>/despachar/', operaciones_views.transferencia_despachar, name='transferencia_ejecutar_despacho'),
    path('operaciones/transferencias/<int:trf_id>/recibir/', operaciones_views.transferencia_recibir, name='transferencia_ejecutar_recepcion'),
    path('operaciones/transferencias/manual/', operaciones_views.transferencia_manual, name='transferencia_manual'),
    
    # Ajustes
    path('operacion/ajustes/', operaciones_views.mov_ajustes, name='mov_ajustes'),

    # ==========================================
    # 7. ADMINISTRACIÓN Y CONTROL DE ACCESO
    # ==========================================
    path('administracion/perfiles/', admin_views.perfiles_consulta, name='perfiles_consulta'),
    path('administracion/perfiles/nuevo/', admin_views.perfil_crear, name='perfil_crear'),
    path('administracion/perfiles/editar/<int:pk>/', admin_views.perfil_editar, name='perfil_editar'),
    path('admin/usuarios/', auth_views.inicio, name='usuarios_gestion'),
    path('admin/reportes/', auth_views.inicio, name='reportes_home'),

    # ==========================================
    # 8. ENDPOINTS API (Asíncronos)
    # ==========================================
    path('api/productos-bodega/', operaciones_views.api_productos_por_bodega, name='api_productos_bodega'),
    path('api/lotes-producto/', operaciones_views.api_lotes_por_producto, name='api_lotes_producto'),
    path('api/producto/nuevo/', operaciones_views.producto_quick_create, name='producto_quick_create'),
]