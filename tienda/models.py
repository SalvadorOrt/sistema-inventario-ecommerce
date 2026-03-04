from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.conf import settings
from django.db.models import Avg

from miapp.models import Producto

User = get_user_model()


class DireccionEnvio(models.Model):
    """
    Permite al usuario guardar múltiples direcciones para el Checkout.
    """
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="direcciones")
    nombre_destinatario = models.CharField(max_length=100, help_text="Quién recibe el paquete")
    calle_principal = models.CharField(max_length=200)
    calle_secundaria = models.CharField(max_length=200, blank=True, null=True)
    ciudad = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20)
    referencia = models.CharField(max_length=300, blank=True, null=True)
    
    es_principal = models.BooleanField(default=False)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Dirección de envío"
        verbose_name_plural = "Direcciones de envío"

    def __str__(self):
        return f"{self.nombre_destinatario} - {self.ciudad}"

    def save(self, *args, **kwargs):
       
        if self.es_principal:
            DireccionEnvio.objects.filter(usuario=self.usuario, es_principal=True).update(es_principal=False)
        super().save(*args, **kwargs)

class Carrito(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name="carrito")
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Carrito de compras"
        verbose_name_plural = "Carritos de compras"

    def __str__(self):
        return f"Carrito de {self.usuario.username}"

    @property
    def total_items(self):
        return sum(item.cantidad for item in self.items.all())

    @property
    def total(self):
        return sum(item.subtotal for item in self.items.all())

    def vaciar(self):
        self.items.all().delete()

class ItemCarrito(models.Model):
    carrito = models.ForeignKey(Carrito, on_delete=models.CASCADE, related_name="items")
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField(default=1)
    agregado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('carrito', 'producto')
        verbose_name = "Item del carrito"
        verbose_name_plural = "Items del carrito"

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre}"

    @property
    def subtotal(self):
        return self.producto.precio_venta * self.cantidad

    def clean(self):
       
        
        super().clean()

    def save(self, *args, **kwargs):
       
        super().save(*args, **kwargs)


class Favorito(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favoritos')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='favoritos_usuarios')
    fecha_agregado = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('usuario', 'producto')
        verbose_name = "Favorito"
        verbose_name_plural = "Favoritos"

    def __str__(self):
        return f"{self.usuario.username} -> {self.producto.nombre}"

class MetodoPago(models.Model):
    
    TIPO_CHOICES = [
        ('VISA', 'Visa'),
        ('MASTERCARD', 'Mastercard'),
        ('DINERS', 'Diners Club'),
        ('AMEX', 'American Express'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="metodos_pago")
    nombre_titular = models.CharField(max_length=100)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    ultimos_digitos = models.CharField(max_length=4, help_text="Solo los últimos 4 números")
    fecha_vencimiento = models.CharField(max_length=5, help_text="Formato MM/YY")
    
    es_predeterminado = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.tipo} terminada en {self.ultimos_digitos}"

    def save(self, *args, **kwargs):
        
        if self.es_predeterminado:
            MetodoPago.objects.filter(usuario=self.usuario, es_predeterminado=True).update(es_predeterminado=False)
        super().save(*args, **kwargs)