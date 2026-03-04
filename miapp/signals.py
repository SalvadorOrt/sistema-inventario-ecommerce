from django.db.models import Sum
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import StockLote, InventarioProducto


def recalcular_stock(bodega, producto):
    total = (
        StockLote.objects.filter(
            producto=producto,
            ubicacion__rack__zona__bodega=bodega,
            archivado=False,
            cantidad_disponible__gt=0,
            estado_lote__es_vendible=True
        )
        .aggregate(total=Sum("cantidad_disponible"))
        .get("total") or 0
    )

    inv, _ = InventarioProducto.objects.get_or_create(
        bodega=bodega,
        producto=producto
    )
    inv.stock_actual = int(total)
    inv.save(update_fields=["stock_actual"])


@receiver(post_save, sender=StockLote)
def stocklote_guardado(sender, instance, **kwargs):
    bodega = instance.ubicacion.rack.zona.bodega
    recalcular_stock(bodega, instance.producto)


@receiver(post_delete, sender=StockLote)
def stocklote_eliminado(sender, instance, **kwargs):
    bodega = instance.ubicacion.rack.zona.bodega
    recalcular_stock(bodega, instance.producto)
