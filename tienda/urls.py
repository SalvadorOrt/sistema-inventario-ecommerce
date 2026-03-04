from django.urls import path
from . import views

app_name = 'tienda'

urlpatterns = [
    # ==========================================
    # 1. LANDING PAGE E INICIO
    # ==========================================
    path('', views.index, name='inicio'),

    # ==========================================
    # 2. GESTIÓN DE ACCESO (AUTH)
    # ==========================================
    path('registro/', views.registro_cliente, name='registro'),
    path('login/', views.login_cliente, name='login'),
    path('logout/', views.logout_cliente, name='logout'),

    # ==========================================
    # 3. NAVEGACIÓN Y CATÁLOGO
    # ==========================================
    path('catalogo/', views.catalogo, name='catalogo'),
    path('producto/<int:producto_id>/', views.producto_detalle, name='producto_detalle'),

    # ==========================================
    # 4. CARRITO DE COMPRAS (MÓDULO DINÁMICO)
    # ==========================================
    path('carrito/', views.ver_carrito, name='ver_carrito'),
    path('agregar/<int:producto_id>/', views.agregar_carrito, name='agregar_carrito'),
    path('carrito/eliminar/<int:item_id>/', views.eliminar_del_carrito, name='eliminar_item'),
    path('carrito/actualizar/<int:item_id>/', views.actualizar_item_carrito, name='actualizar_item'),

    # ==========================================
    # 5. LISTA DE DESEOS (WISHLIST)
    # ==========================================
    path('favoritos/', views.ver_favoritos, name='ver_favoritos'),
    path('favoritos/toggle/<int:producto_id>/', views.toggle_favorito, name='toggle_favorito'),

    # ==========================================
    # 6. PROCESO DE COMPRA (CHECKOUT)
    # ==========================================
    path('checkout/', views.checkout, name='checkout'),
    path('checkout/procesar/', views.procesar_compra, name='procesar_compra'),
    path('compra-exitosa/<int:pedido_id>/', views.compra_exitosa, name='compra_exitosa'),

    # ==========================================
    # 7. PANEL DE CLIENTE (MI CUENTA)
    # ==========================================
    # Perfil y Resumen
    path('mi-perfil/', views.mi_perfil, name='mi_perfil'),
    
    # Historial de Pedidos y Detalles
    path('mis-pedidos/', views.mis_pedidos, name='mis_pedidos'),
    path('mi-cuenta/pedido/<int:pedido_id>/', views.detalle_compra, name='detalle_compra'),

    # Direcciones de Entrega
    path('direccion/agregar/', views.agregar_direccion, name='agregar_direccion'),
    path('direccion/eliminar/<int:direccion_id>/', views.eliminar_direccion, name='eliminar_direccion'),

    # Métodos de Pago Guardados
    path('pago/agregar/', views.agregar_metodo_pago, name='agregar_pago'),
    path('pago/eliminar/<int:pago_id>/', views.eliminar_metodo_pago, name='eliminar_pago'),
]