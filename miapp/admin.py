from django.contrib import admin
from django.utils.html import format_html
from .models import (
    PerfilUsuario, Pais, TipoIdentificacion, TipoAlmacenamiento,
    EstadoPedido, Impuesto, TipoMovimiento, ClaseProducto, TipoCliente,
    PerfilCaducidad, EstadoLote, Marca, Categoria, Proveedor, Producto, 
    ImagenProducto, Bodega, ZonaAlmacenamiento, Rack, UbicacionFisica,
    InventarioProducto, StockLote, Cliente, Pedido, DetallePedido,
    MovimientoInventario, TransferenciaInterna, DetalleTransferenciaInterna
)


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False



@admin.register(Marca)
class MarcaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "es_activo")
    search_fields = ("nombre",)  

@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ("nombre", "pais", "numero_identificacion", "es_activo")
    search_fields = ("nombre", "numero_identificacion") 
@admin.register(Impuesto)
class ImpuestoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "porcentaje", "es_activo")
    search_fields = ("nombre",) 

@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "prefijo_sku", "es_activo")
    search_fields = ("nombre", "prefijo_sku") 
@admin.register(UbicacionFisica)
class UbicacionFisicaAdmin(admin.ModelAdmin):
    list_display = ("codigo_celda", "rack", "nivel_fila", "es_activo")
    search_fields = ("codigo_celda",) 
    list_filter = ("rack__zona__bodega", "es_activo")



class ImagenProductoInline(admin.TabularInline):
    model = ImagenProducto
    extra = 1

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("codigo_sku", "nombre", "categoria", "precio_venta", "es_activo")
   
    list_filter = ("categoria", "marca", "es_activo") 
    search_fields = ("codigo_sku", "nombre", "codigo_barras")
    readonly_fields = ("codigo_sku", "fecha_creacion", "fecha_actualizacion")
    
    autocomplete_fields = ("categoria", "marca", "impuesto") 
    
    inlines = [ImagenProductoInline]

@admin.register(StockLote)
class StockLoteAdmin(admin.ModelAdmin):
    list_display = ("lote", "producto", "ubicacion", "cantidad_disponible", "estado_lote")
    list_filter = ("estado_lote", "archivado")
    search_fields = ("lote", "producto__nombre")
    readonly_fields = ("lote", "lote_origen", "costo_compra_lote")
    autocomplete_fields = ("producto", "ubicacion", "proveedor")



@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ("user", "rol_negocio", "bodega")
    search_fields = ("user__username",)

@admin.register(InventarioProducto)
class InventarioProductoAdmin(admin.ModelAdmin):
    list_display = ("producto", "bodega", "stock_actual", "stock_minimo")
    readonly_fields = ("stock_actual", "fecha_ultimo_movimiento")

class DetallePedidoInline(admin.TabularInline):
    model = DetallePedido
    extra = 0
    readonly_fields = ("subtotal", "ganancia", "total_linea")

@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "cliente", "estado_pedido", "total", "fecha_creacion")
    readonly_fields = ("codigo", "subtotal", "monto_iva", "total", "total_costo", "ganancia_total")
    inlines = [DetallePedidoInline]

@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(ReadOnlyAdmin):
    list_display = ("codigo", "tipo_movimiento", "cantidad", "fecha")

@admin.register(TransferenciaInterna)
class TransferenciaInternaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "bodega_origen", "bodega_destino", "estado")


admin.site.register(Pais)
admin.site.register(TipoIdentificacion)
admin.site.register(TipoAlmacenamiento)
admin.site.register(EstadoPedido)
admin.site.register(ClaseProducto)
admin.site.register(TipoCliente)
admin.site.register(PerfilCaducidad)
admin.site.register(Bodega)
admin.site.register(ZonaAlmacenamiento)
admin.site.register(Rack)
admin.site.register(Cliente)