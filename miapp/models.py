
from __future__ import annotations
import unicodedata
from decimal import Decimal
from datetime import timedelta
from typing import List, Optional, TYPE_CHECKING


from django.db import models, transaction, IntegrityError
from django.db.models import Q, F, Sum, Value
from django.db.models.functions import Lower, Coalesce
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.core.exceptions import ValidationError


from django.contrib.auth import get_user_model


User = get_user_model()

class PerfilUsuario(models.Model):
    class RolNegocio(models.TextChoices):
        ADMIN_SISTEMA = "ADMIN_SISTEMA", "ADMIN_SISTEMA"
        OPERADOR_OPERACIONES = "OPERADOR_OPERACIONES", "OPERADOR_OPERACIONES"
        VENDEDOR = "VENDEDOR", "VENDEDOR"
        CLIENTE = "CLIENTE", "CLIENTE WEB"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="perfil")
    rol_negocio = models.CharField(max_length=30, choices=RolNegocio.choices)
   
    bodega = models.ForeignKey("Bodega", on_delete=models.PROTECT, null=True, blank=True, related_name="usuarios")

    class Meta:
        verbose_name = "Perfil de usuario"
        verbose_name_plural = "Perfiles de usuario"
        indexes = [
            models.Index(fields=["rol_negocio"]),
            models.Index(fields=["bodega"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.rol_negocio}"


    def es_admin(self) -> bool:
        return self.rol_negocio == self.RolNegocio.ADMIN_SISTEMA

    def es_operador(self) -> bool:
        return self.rol_negocio == self.RolNegocio.OPERADOR_OPERACIONES

    def es_vendedor(self) -> bool:
        return self.rol_negocio == self.RolNegocio.VENDEDOR

    def es_cliente(self) -> bool:
        
        return self.rol_negocio == self.RolNegocio.CLIENTE

    def clean(self):
       
        if (self.rol_negocio == self.RolNegocio.OPERADOR_OPERACIONES 
            and not self.bodega
        ):
            raise ValidationError(
                "El usuario con rol OPERADOR_OPERACIONES debe tener una bodega asignada."
            )
        
        
        if self.rol_negocio == self.RolNegocio.CLIENTE and self.bodega:
            raise ValidationError(
                "Un CLIENTE WEB no puede tener una bodega física asignada."
            )

        super().clean()


@receiver(post_save, sender=User)
def crear_perfil_usuario(sender, instance, created, **kwargs):
    if created:
        if instance.is_superuser:
            rol = PerfilUsuario.RolNegocio.ADMIN_SISTEMA
        else:
            rol = PerfilUsuario.RolNegocio.CLIENTE
        PerfilUsuario.objects.get_or_create(
            user=instance, 
            defaults={'rol_negocio': rol}
        )


class Pais(models.Model):
    codigo_iso = models.CharField(max_length=10, unique=True) 
    nombre = models.CharField(max_length=100, unique=True)
    es_activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "País"
        verbose_name_plural = "Países"
        constraints = [
            models.UniqueConstraint(Lower("codigo_iso"), name="unique_pais_codigo_ci"),
            models.UniqueConstraint(Lower("nombre"), name="unique_pais_nombre_ci"),
        ]
        indexes = [models.Index(fields=["es_activo"])]

    def __str__(self):
        return f"{self.nombre} ({self.codigo_iso})"

    def save(self, *args, **kwargs):
        if isinstance(self.codigo_iso, str):
            self.codigo_iso = self.codigo_iso.strip().upper()
        if isinstance(self.nombre, str):
            self.nombre = self.nombre.strip().title()
        super().save(*args, **kwargs)


class TipoIdentificacion(models.Model):
    codigo = models.CharField(max_length=90, unique=True) 
    descripcion = models.CharField(max_length=120)
    es_activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Tipo de identificación"
        verbose_name_plural = "Tipos de identificación"
        constraints = [models.UniqueConstraint(Lower("codigo"), name="unique_tipoident_codigo_ci")]
        indexes = [models.Index(fields=["es_activo"])]

    def __str__(self):
        return self.codigo

    def save(self, *args, **kwargs):
        if isinstance(self.codigo, str):
            self.codigo = self.codigo.strip().upper()
        if isinstance(self.descripcion, str):
            self.descripcion = self.descripcion.strip()
        super().save(*args, **kwargs)


class TipoAlmacenamiento(models.Model):
    codigo = models.CharField(max_length=90, unique=True) 
    descripcion = models.CharField(max_length=150)
    es_activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Tipo de almacenamiento"
        verbose_name_plural = "Tipos de almacenamiento"
        constraints = [models.UniqueConstraint(Lower("codigo"), name="unique_tipoalm_codigo_ci")]
        indexes = [models.Index(fields=["es_activo"])]

    def __str__(self):
        return self.codigo

    def save(self, *args, **kwargs):
        if isinstance(self.codigo, str):
            self.codigo = self.codigo.strip().upper()
        if isinstance(self.descripcion, str):
            self.descripcion = self.descripcion.strip()
        super().save(*args, **kwargs)


class EstadoPedido(models.Model):

    CODIGO_SOLICITADO = 'SOLICITADO'
    CODIGO_PREPARACION = 'PREPARACION' 
    CODIGO_LISTO_DESPACHO = 'LISTO_PARA_DESPACHO'
    CODIGO_ENTREGADO = 'ENTREGADO'
    CODIGO_ANULADO = 'ANULADO'
    CODIGO_BACKORDER = 'BACKORDER'
    CODIGO_PARCIAL = 'ENTREGA_PARCIAL'
    class EtapaLogica(models.TextChoices):
        SOLICITUD = "SOLICITUD", "Pendiente de Procesar"
        PICKING   = "PREPARACION", "En Preparación / Despachando"
        CERRADO   = "CERRADO",   "Finalizado o Entregado"
        ANULADO   = "ANULADO",   "Anulado"
    codigo = models.CharField(max_length=90, unique=True)  
    descripcion = models.CharField(max_length=150, blank=True, null=True)
    es_activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Estado de pedido"
        verbose_name_plural = "Estados de pedido"
        constraints = [models.UniqueConstraint(Lower("codigo"), name="unique_estadopedido_codigo_ci")]
        indexes = [models.Index(fields=["es_activo"])]

    def __str__(self):
        return self.codigo

    def save(self, *args, **kwargs):
        if isinstance(self.codigo, str):
            self.codigo = self.codigo.strip().upper()
        if isinstance(self.descripcion, str):
            self.descripcion = self.descripcion.strip() or None
        super().save(*args, **kwargs)

class Impuesto(models.Model):
    nombre = models.CharField(max_length=50)
    porcentaje = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        
    )
    es_activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombre} ({self.porcentaje}%)"

class TipoMovimiento(models.Model):

    CODIGO_VENTA = 'DESPACHO_PEDIDO'      
    CODIGO_COMPRA = 'COMPRA_PROVEEDOR'     
    CODIGO_AJUSTE_POS = 'AJUSTE_POS'       
    CODIGO_AJUSTE_NEG = 'AJUSTE_NEGATIVO'  
    CODIGO_INV_INICIAL = 'INVENTARIO_INICIAL' 
    CODIGO_TRF_ENTRADA = 'TRANSFERENCIA_ENTRADA'
    CODIGO_TRF_SALIDA = 'TRANSFERENCIA_SALIDA'

    codigo = models.CharField(
        max_length=50, 
        unique=True, 
    )
    descripcion = models.CharField(max_length=200, blank=True, null=True)
    
   
    es_activo = models.BooleanField(default=True)
    afecta_stock = models.BooleanField(default=True)
    es_entrada = models.BooleanField(default=False)
    es_salida = models.BooleanField(default=False)

   
    es_sistema = models.BooleanField(
        default=False, 
        editable=False,
        
    )

    
    requiere_pedido = models.BooleanField(default=False)
    requiere_motivo_detallado = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Tipo de movimiento"
        verbose_name_plural = "Tipos de movimiento"
        constraints = [
            models.UniqueConstraint(Lower("codigo"), name="unique_tipomov_codigo_ci")
        ]
        indexes = [
            models.Index(fields=["es_activo"]),
            models.Index(fields=["es_entrada"]),
            models.Index(fields=["es_salida"]),
        ]

    def __str__(self):
        return f"{self.codigo}"

    def clean(self):
        
        if self.es_entrada and self.es_salida:
            raise ValidationError("No puede ser entrada y salida a la vez.")
        if self.afecta_stock and not (self.es_entrada or self.es_salida):
            raise ValidationError("Si afecta stock, debe definir si entra o sale.")
        super().clean()

    def save(self, *args, **kwargs):
        
        if self.codigo:
            self.codigo = self.codigo.strip().upper()
        self.full_clean()
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
       
        if self.es_sistema:
            raise ValidationError(f"No se puede eliminar '{self.codigo}' porque es un registro de sistema.")
        super().delete(*args, **kwargs)


class ClaseProducto(models.Model):
    codigo = models.CharField(max_length=30, unique=True) 
    descripcion = models.CharField(max_length=150)
    es_activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Clase de producto"
        verbose_name_plural = "Clases de producto"
        constraints = [models.UniqueConstraint(Lower("codigo"), name="unique_claseprod_codigo_ci")]
        indexes = [models.Index(fields=["es_activo"])]

    def __str__(self):
        return self.codigo

    def save(self, *args, **kwargs):
        if isinstance(self.codigo, str):
            self.codigo = self.codigo.strip().upper()
        if isinstance(self.descripcion, str):
            self.descripcion = self.descripcion.strip()
        super().save(*args, **kwargs)


class TipoCliente(models.Model):
    codigo = models.CharField(max_length=40, unique=True)  
    descripcion = models.CharField(max_length=150)
    es_activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Tipo de cliente"
        verbose_name_plural = "Tipos de cliente"
        constraints = [models.UniqueConstraint(Lower("codigo"), name="unique_tipocliente_codigo_ci")]
        indexes = [models.Index(fields=["es_activo"])]

    def __str__(self):
        return self.codigo

    def save(self, *args, **kwargs):
        if isinstance(self.codigo, str):
            self.codigo = self.codigo.strip().upper()
        if isinstance(self.descripcion, str):
            self.descripcion = self.descripcion.strip()
        super().save(*args, **kwargs)


class PerfilCaducidad(models.Model):
    codigo = models.CharField(max_length=50, unique=True)
    descripcion = models.CharField(max_length=200)
    requiere_caducidad = models.BooleanField(default=True)
    dias_bloqueo_previo = models.PositiveIntegerField(
        default=0, 
      
    )
    
   
    estrategia_requerida = models.CharField(
        max_length=10,
        choices=[("FIFO", "FIFO"), ("FEFO", "FEFO")],
        blank=True,
        null=True,
       
    )
    
    es_activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Perfil de caducidad"
        verbose_name_plural = "Perfiles de caducidad"
        constraints = [
            models.UniqueConstraint(Lower("codigo"), name="unique_perfilcaducidad_codigo_ci")
        ]
        indexes = [
            models.Index(fields=["es_activo"]),
            models.Index(fields=["requiere_caducidad"]),
        ]

    def __str__(self):
        estrategia = f" | {self.estrategia_requerida}" if self.estrategia_requerida else ""
        return f"{self.codigo} ({self.dias_bloqueo_previo}d{estrategia})"

    def clean(self):
        if not self.requiere_caducidad:
            if (self.dias_bloqueo_previo or 0) > 0:
                raise ValidationError("Si requiere_caducidad=False, dias_bloqueo_previo debe ser 0.")
            if self.estrategia_requerida == "FEFO":
                raise ValidationError("No se puede exigir FEFO en un perfil que no requiere caducidad.")
        super().clean()

    def save(self, *args, **kwargs):
        if isinstance(self.codigo, str):
            self.codigo = self.codigo.strip().upper()
        if isinstance(self.descripcion, str):
            self.descripcion = self.descripcion.strip()
        self.full_clean()
        super().save(*args, **kwargs)

class EstadoLote(models.Model):
    
    CODIGO_DISPONIBLE = 'DISPONIBLE'   
    CODIGO_CUARENTENA = 'CUARENTENA'  
    CODIGO_CADUCADO = 'CADUCADO'      
    CODIGO_AGOTADO = 'AGOTADO'         
    CODIGO_MAL_ESTADO = 'MAL_ESTADO'   
    CODIGO_RECHAZADO = 'RECHAZADO'    
    CODIGO_RESERVADO = 'RESERVADO'    
    CODIGO_MUESTRA = 'MUESTRA'         

    codigo = models.CharField(max_length=30, unique=True)
    descripcion = models.CharField(max_length=150, blank=True, null=True)

    es_vendible = models.BooleanField(
        default=True,
        
    )
    es_activo = models.BooleanField(default=True)

    
    marca_disponible = models.BooleanField(default=False)
    marca_agotado = models.BooleanField(default=False)
    marca_bloqueado = models.BooleanField(default=False)
    marca_vencido = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Estado de lote"
        verbose_name_plural = "Estados de lote"
        constraints = [
            models.UniqueConstraint(Lower("codigo"), name="unique_estadolote_codigo_ci")
        ]
        indexes = [
            models.Index(fields=["es_activo"]),
            models.Index(fields=["es_vendible"]),
           
            models.Index(fields=["marca_disponible"]),
            models.Index(fields=["marca_agotado"]),
            models.Index(fields=["marca_vencido"]),
        ]

    def __str__(self):
        return self.codigo

    def clean(self):
        
        if (self.marca_vencido or self.marca_bloqueado) and self.es_vendible:
            raise ValidationError(f"El estado {self.codigo} no puede ser vendible si está marcado como Vencido o Bloqueado.")

      
        if self.marca_disponible and not self.es_vendible:
            raise ValidationError("El estado marcado como 'marca_disponible' debe ser obligatoriamente vendible.")

      
        flags = [self.marca_disponible, self.marca_agotado, self.marca_bloqueado, self.marca_vencido]
        if flags.count(True) > 1:
            raise ValidationError("Un estado no puede tener múltiples marcas de automatización simultáneas (Ej: No puede ser Vencido y Disponible a la vez).")

    def save(self, *args, **kwargs):
       
        if isinstance(self.codigo, str):
            self.codigo = self.codigo.strip().upper()
        if isinstance(self.descripcion, str):
            self.descripcion = self.descripcion.strip() or None

       
        self.full_clean()

        
        if self.marca_disponible:
            EstadoLote.objects.filter(marca_disponible=True).exclude(pk=self.pk).update(marca_disponible=False)
        
        if self.marca_agotado:
            EstadoLote.objects.filter(marca_agotado=True).exclude(pk=self.pk).update(marca_agotado=False)
            
        if self.marca_vencido:
            EstadoLote.objects.filter(marca_vencido=True).exclude(pk=self.pk).update(marca_vencido=False)

       

        super().save(*args, **kwargs)



class Marca(models.Model):
    nombre = models.CharField(max_length=150, unique=True)
    descripcion = models.CharField(max_length=500, blank=True, null=True)
    es_activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Marca"
        verbose_name_plural = "Marcas"
        constraints = [models.UniqueConstraint(Lower("nombre"), name="unique_marca_nombre_ci")]
        indexes = [models.Index(fields=["es_activo"])]

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        if isinstance(self.nombre, str):
            self.nombre = self.nombre.strip().title()
        if isinstance(self.descripcion, str):
            self.descripcion = self.descripcion.strip() or None
        super().save(*args, **kwargs)


class Categoria(models.Model):
    nombre = models.CharField(max_length=150, unique=True)
    descripcion = models.CharField(max_length=500, blank=True, null=True)

    prefijo_sku = models.CharField(max_length=10, unique=True)
    es_activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"
        constraints = [
            models.UniqueConstraint(Lower("nombre"), name="unique_categoria_nombre_ci"),
            models.UniqueConstraint(Lower("prefijo_sku"), name="unique_categoria_prefijo_ci"),
        ]
        indexes = [models.Index(fields=["es_activo"])]

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        if isinstance(self.nombre, str):
            self.nombre = self.nombre.strip().title()
        if isinstance(self.descripcion, str):
            self.descripcion = self.descripcion.strip() or None
        if isinstance(self.prefijo_sku, str):
            self.prefijo_sku = self.prefijo_sku.strip().upper()
        super().save(*args, **kwargs)
class Proveedor(models.Model):
    nombre = models.CharField(max_length=200, unique=True)

    tipo_identificacion = models.ForeignKey(TipoIdentificacion, on_delete=models.PROTECT, related_name="proveedores")
    numero_identificacion = models.CharField(max_length=30, unique=True)

    pais = models.ForeignKey(Pais, on_delete=models.PROTECT, related_name="proveedores")

    telefono = models.CharField(max_length=30, blank=True, null=True)
    correo = models.EmailField(max_length=150, blank=True, null=True)
    direccion = models.CharField(max_length=300, blank=True, null=True)

    es_activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"
        constraints = [
            models.UniqueConstraint(Lower("nombre"), name="unique_proveedor_nombre_ci"),
            models.UniqueConstraint(Lower("numero_identificacion"), name="unique_proveedor_ident_ci"),
        ]
        indexes = [
            models.Index(fields=["es_activo"]),
            models.Index(fields=["pais"]),
        ]

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        if isinstance(self.nombre, str):
            self.nombre = self.nombre.strip().title()
        if isinstance(self.numero_identificacion, str):
            self.numero_identificacion = self.numero_identificacion.strip()
        if isinstance(self.telefono, str):
            self.telefono = self.telefono.strip() or None
        if isinstance(self.correo, str):
            self.correo = self.correo.strip() or None
        if isinstance(self.direccion, str):
            self.direccion = self.direccion.strip() or None
        super().save(*args, **kwargs)

class Producto(models.Model):
    class EstrategiaSalida(models.TextChoices):
        FIFO = "FIFO", "First In, First Out (Primero en Entrar)"
        FEFO = "FEFO", "First Expired, First Out (Primero en Vencer)"
    codigo_sku = models.CharField(max_length=100, unique=True, null=True, blank=True)
    codigo_barras = models.CharField(max_length=50, blank=True, null=True)
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)
    es_publico = models.BooleanField(default=True, verbose_name="Vender en la web")
    impuesto = models.ForeignKey(
        'Impuesto', 
        on_delete=models.PROTECT,
        related_name="productos"
    )
    precio_venta = models.DecimalField(
        max_digits=18, decimal_places=2
    )
    costo_compra = models.DecimalField(
        max_digits=18, decimal_places=2, default=0
    )
    marca = models.ForeignKey("Marca", on_delete=models.PROTECT, related_name="productos")
    categoria = models.ForeignKey("Categoria", on_delete=models.PROTECT, related_name="productos")
    tipo_almacenamiento = models.ForeignKey("TipoAlmacenamiento", on_delete=models.PROTECT, related_name="productos")
    clase_producto = models.ForeignKey("ClaseProducto", on_delete=models.PROTECT, related_name="productos")
    
    perfil_caducidad = models.ForeignKey(
        'PerfilCaducidad',
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="productos",
    )
    
    estrategia_salida = models.CharField(
        max_length=10,
        choices=EstrategiaSalida.choices,
        default=EstrategiaSalida.FIFO,
       
    )

    notas_manejo = models.CharField(max_length=300, blank=True, null=True)
    es_activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        constraints = [
            models.UniqueConstraint(Lower("codigo_sku"), name="unique_producto_sku_ci"),
            
            models.CheckConstraint(
                condition=Q(precio_venta__gte=0), 
                name="ck_producto_precio_venta_no_neg"
            ),
            models.CheckConstraint(
                condition=Q(costo_compra__gte=0), 
                name="ck_producto_costo_compra_no_neg"
            ),
        ]
        indexes = [
            models.Index(fields=["es_activo"]),
            models.Index(fields=["categoria", "marca"]),
            models.Index(fields=["perfil_caducidad"]),
            models.Index(fields=["estrategia_salida"]),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.codigo_sku or 'SIN-SKU'})"

    def clean(self):
        super().clean()
        if not self.codigo_sku and (not self.categoria_id or not self.marca_id):
            raise ValidationError("Para autogenerar SKU debes tener marca y categoría.")
        if self.perfil_caducidad_id and self.perfil_caducidad.estrategia_requerida:
            requerida = self.perfil_caducidad.estrategia_requerida
            if self.estrategia_salida != requerida:
                raise ValidationError({
                    'estrategia_salida': (
                        f"El perfil '{self.perfil_caducidad.codigo}' exige la estrategia {requerida}. "
                        f"No se permite {self.estrategia_salida} para este tipo de producto."
                    )
                })

    def save(self, *args, **kwargs):
        
        if isinstance(self.nombre, str):
            self.nombre = self.nombre.strip().title()
        if isinstance(self.codigo_sku, str):
            self.codigo_sku = self.codigo_sku.strip().upper() or None
        if self.precio_venta:
            self.precio_venta = Decimal(self.precio_venta).quantize(Decimal('0.00'))
        self.full_clean()
        self.precio_venta = Decimal(str(self.precio_venta)).quantize(Decimal("0.01"))
        self.costo_compra = Decimal(str(self.costo_compra)).quantize(Decimal("0.01"))
        if not self.codigo_sku and self.categoria_id and self.marca_id:
            self.codigo_sku = self._generar_siguiente_sku()
        for _ in range(5):
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                if self.categoria_id and self.marca_id and not kwargs.get("update_fields"):
                    self.codigo_sku = self._generar_siguiente_sku()
                    continue
                raise
        raise IntegrityError("No se pudo generar un SKU único tras varios intentos.")

    def _normalizar_codigo(self, texto: str, length: int = 3) -> str:
        if not texto: return "X" * length
        texto_norm = unicodedata.normalize("NFKD", texto)
        texto_ascii = texto_norm.encode("ascii", "ignore").decode("ascii")
        texto_ascii = texto_ascii.upper().replace(" ", "").replace("-", "")
        return texto_ascii[:length].ljust(length, "X")

    def _generar_siguiente_sku(self) -> str:
        cat_base = getattr(self.categoria, 'prefijo_sku', None) or self.categoria.nombre
        prefijo_cat = self._normalizar_codigo(cat_base, 3)
        marca_cod = self._normalizar_codigo(self.marca.nombre, 3)
        base = f"{prefijo_cat}-{marca_cod}-"
        
        ultimo = (
            Producto.objects
            .filter(categoria=self.categoria, marca=self.marca, codigo_sku__startswith=base)
            .order_by("-codigo_sku")
            .first()
        )
        
        correlativo = 1
        if ultimo and ultimo.codigo_sku:
            try:
                correlativo = int(ultimo.codigo_sku.split("-")[-1]) + 1
            except (ValueError, IndexError):
                pass
        return f"{base}{str(correlativo).zfill(4)}"
    
class ImagenProducto(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="imagenes")
    imagen = models.ImageField(upload_to="productos/", blank=True, null=True)
    orden = models.IntegerField(default=0)
    es_principal = models.BooleanField(default=False)
    fecha_registro = models.DateTimeField(default=timezone.now)
    class Meta:
        verbose_name = "Imagen de producto"
        verbose_name_plural = "Imágenes de producto"
        ordering = ['orden'] 
        indexes = [
            models.Index(fields=["producto", "orden"]),
        ]

    def __str__(self):
        return f"Imagen {self.id} de {self.producto_id}"

    def save(self, *args, **kwargs):
        if self.orden == 0:
            self.es_principal = True
        else:
            self.es_principal = False
            
        super().save(*args, **kwargs)


class Bodega(models.Model):
    nombre = models.CharField(max_length=200, unique=True)
    direccion = models.CharField(max_length=300, blank=True, null=True)
    referencia = models.CharField(max_length=300, blank=True, null=True)
    es_activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Bodega"
        verbose_name_plural = "Bodegas"
        constraints = [
            models.UniqueConstraint(Lower("nombre"), name="unique_bodega_nombre_ci")
        ]
        indexes = [
            models.Index(fields=["es_activo"]),
        ]

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        if isinstance(self.nombre, str):
            self.nombre = self.nombre.strip().title()
        if isinstance(self.direccion, str):
            self.direccion = self.direccion.strip() or None
        if isinstance(self.referencia, str):
            self.referencia = self.referencia.strip() or None
        super().save(*args, **kwargs)


    def obtener_rentabilidad(self):
        from miapp.models import MovimientoInventario, DetallePedido 
 
        data = MovimientoInventario.objects.filter(
            inventario__bodega=self,
            tipo_movimiento__es_salida=True,
            pedido__isnull=False
        ).aggregate(
            total_unidades=Sum('cantidad'),
            total_costos=Sum('valor_total'),
           
            total_ingresos=Sum(
                F('cantidad') * F('pedido__detalles__precio_unitario'),
                filter=Q(pedido__detalles__producto=F('stock_lote__producto'))
            )
        )

        ingresos = data['total_ingresos'] or Decimal("0.00")
        costos = data['total_costos'] or Decimal("0.00")

        return {
            'unidades_despachadas': data['total_unidades'] or 0,
            'ingresos': ingresos.quantize(Decimal("0.01")),
            'costos': costos.quantize(Decimal("0.01")),
            'utilidad_neta': (ingresos - costos).quantize(Decimal("0.01")),
        }


class ZonaAlmacenamiento(models.Model):
    bodega = models.ForeignKey(Bodega, on_delete=models.CASCADE, related_name="zonas")
    codigo = models.CharField(max_length=10, editable=False) 
    nombre = models.CharField(max_length=100)
    tipo_almacenamiento = models.ForeignKey("TipoAlmacenamiento", on_delete=models.PROTECT, related_name="zonas")
    es_activo = models.BooleanField(default=True)
    class Meta:
        verbose_name = "Zona de almacenamiento"
        verbose_name_plural = "Zonas de almacenamiento"
        constraints = [
            models.UniqueConstraint(fields=["bodega", "codigo"], name="unique_zona_bodega_codigo"),
            models.UniqueConstraint(fields=["bodega", "nombre"], name="unique_zona_bodega_nombre_ci"),
        ]
        indexes = [
            models.Index(fields=["es_activo"]),
            models.Index(fields=["bodega", "nombre"]),
        ]

    def __str__(self):
        return f"{self.bodega.nombre} - {self.nombre} ({self.codigo})"

    def _generar_codigo_zona(self) -> str:
      
        total_zonas = ZonaAlmacenamiento.objects.filter(bodega=self.bodega).count()
        
        siguiente = total_zonas + 1
       
        return f"Z-{str(siguiente).zfill(2)}"

    def save(self, *args, **kwargs):
        if isinstance(self.nombre, str):
            self.nombre = self.nombre.strip().title()
        
        
        if not self.codigo and self.bodega_id:
            self.codigo = self._generar_codigo_zona()

        try:
            super().save(*args, **kwargs)
        except Exception: 
           
            if not self.pk:
                total_zonas = ZonaAlmacenamiento.objects.filter(bodega=self.bodega).count()
                self.codigo = f"Z-{str(total_zonas + 2).zfill(2)}" 
                super().save(*args, **kwargs)

class Rack(models.Model):
    zona = models.ForeignKey(ZonaAlmacenamiento, on_delete=models.CASCADE, related_name="racks")
    codigo = models.CharField(max_length=90, editable=False) 
    descripcion = models.CharField(max_length=200, blank=True, null=True)
    es_activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Rack"
        verbose_name_plural = "Racks"
        constraints = [models.UniqueConstraint(fields=["zona", "codigo"], name="unique_rack_zona_codigo")]
        indexes = [
            models.Index(fields=["es_activo"]),
            models.Index(fields=["zona", "codigo"]),
        ]

    def __str__(self):
        return f"{self.zona} / Rack {self.codigo}"

    @staticmethod
    def _numero_a_letras(n: int) -> str:
        res = ""
        while n > 0:
            n, rem = divmod(n - 1, 26)
            res = chr(65 + rem) + res
        return res

    @staticmethod
    def _letras_a_numero(s: str) -> int:
        n = 0
        for c in s:
            n = n * 26 + (ord(c) - 64)
        return n

    def _generar_siguiente_codigo(self) -> str:
        
        racks_existentes = Rack.objects.filter(zona=self.zona)
        
        max_valor = 0
        
        
        for r in racks_existentes:
            
            if r.codigo and r.codigo.isalpha():
                try:
                    valor_actual = self._letras_a_numero(r.codigo)
                    if valor_actual > max_valor:
                        max_valor = valor_actual
                except ValueError:
                    continue 
        siguiente = max_valor + 1
        
        return self._numero_a_letras(siguiente)

    def save(self, *args, **kwargs):
        if isinstance(self.descripcion, str):
            self.descripcion = self.descripcion.strip() or None
        if not self.codigo and self.zona_id:
            self.codigo = self._generar_siguiente_codigo()
        for _ in range(5):
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                if self.zona_id and not self.pk:
                    self.codigo = self._generar_siguiente_codigo()
                    continue
                raise
        raise IntegrityError("No se pudo generar un código de rack único tras varios intentos.")


class UbicacionFisica(models.Model):
    rack = models.ForeignKey(Rack, on_delete=models.CASCADE, related_name="ubicaciones")
    nivel_fila = models.PositiveIntegerField() 
    codigo_celda = models.CharField(max_length=30, unique=True, editable=False)
    es_activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Ubicación física"
        verbose_name_plural = "Ubicaciones físicas"
        constraints = [
            models.UniqueConstraint(fields=["rack", "nivel_fila"], name="unique_ubicacion_rack_nivel"),
            models.CheckConstraint(condition=Q(nivel_fila__gte=1), name="ck_ubicacion_nivel_fila_gte_1"),
        ]
        indexes = [
            models.Index(fields=["codigo_celda"]),
            models.Index(fields=["es_activo"]),
            models.Index(fields=["rack", "nivel_fila"]),
        ]
    def __str__(self):
        estado = "OCUPADA" if not self.esta_libre() else "VACÍA"
        return f"{self.codigo_celda} ({estado})"

    def save(self, *args, **kwargs):
        bod = str(self.rack.zona.bodega_id).zfill(2)
        zon = self.rack.zona.codigo.upper()
        rac = self.rack.codigo.upper()
        niv = str(self.nivel_fila).zfill(2)
        self.codigo_celda = f"B{bod}-{zon}-{rac}-N{niv}"
        super().save(*args, **kwargs)

    def obtener_stock_actual(self) -> int:
        return self.lotes.filter(
            archivado=False, 
            cantidad_disponible__gt=0
        ).aggregate(
            total=models.Sum('cantidad_disponible')
        )['total'] or 0

    def esta_libre(self) -> bool:
       
        return self.obtener_stock_actual() == 0

class InventarioProducto(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="inventarios")
    bodega = models.ForeignKey(Bodega, on_delete=models.CASCADE, related_name="inventarios")

    stock_actual = models.IntegerField(default=0)
    stock_minimo = models.IntegerField(default=0)
    stock_seguridad = models.IntegerField(default=0)
    fecha_ultimo_movimiento = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "Inventario de producto"
        verbose_name_plural = "Inventarios de producto"
        constraints = [
            models.UniqueConstraint(fields=["producto", "bodega"], name="unique_inventario_producto_bodega"),
            models.CheckConstraint(condition=Q(stock_actual__gte=0), name="ck_inventario_stock_actual_no_neg"),
            models.CheckConstraint(condition=Q(stock_minimo__gte=0), name="ck_inventario_stock_minimo_no_neg"),
            models.CheckConstraint(condition=Q(stock_seguridad__gte=0), name="ck_inventario_stock_seguridad_no_neg"),
        ]
        indexes = [models.Index(fields=["bodega", "producto"])]

    def __str__(self):
        return f"{self.producto} - {self.bodega} (stock: {self.stock_actual})"

    def _qs_lotes_operativos(self):
        
        from django.utils import timezone
        from datetime import timedelta
        qs = StockLote.objects.select_for_update().filter(
            producto=self.producto,
            archivado=False,
            cantidad_disponible__gt=0,
            ubicacion__rack__zona__bodega=self.bodega,
            estado_lote__es_vendible=True,
            ubicacion__es_activo=True,
            ubicacion__rack__es_activo=True,
            ubicacion__rack__zona__es_activo=True
        )

       
        if self.producto.perfil_caducidad and self.producto.perfil_caducidad.requiere_caducidad:
            dias_buffer = self.producto.perfil_caducidad.dias_bloqueo_previo or 0
            limite_seguridad = timezone.now().date() + timedelta(days=dias_buffer)
            qs = qs.filter(fecha_caducidad__gte=limite_seguridad)

        return qs

    def _ordenar_lotes_por_regla_producto(self, qs):
        
        if self.producto.perfil_caducidad and self.producto.perfil_caducidad.estrategia_requerida:
            estrategia = self.producto.perfil_caducidad.estrategia_requerida
        else:
            estrategia = getattr(self.producto, 'estrategia_salida', 'FEFO')
            
        if estrategia == "FEFO":
            return qs.order_by(F("fecha_caducidad").asc(nulls_last=True), "id")
        return qs.order_by("fecha_entrada", "id")
    
    def obtener_stock_actual(self) -> int:
        return self.lotes.filter(
            archivado=False, 
            cantidad_disponible__gt=0
        ).aggregate(
            total=models.Sum('cantidad_disponible')
        )['total'] or 0

    def esta_libre(self) -> bool:
        return self.obtener_stock_actual() == 0
    
    def productos_en_riesgo(self, bodega):
        return InventarioProducto.objects.filter(
            bodega=bodega,
            stock_actual__lte=F('stock_minimo') 
        ).select_related('producto').annotate(
            deficit=F('stock_minimo') - F('stock_actual')
        ).order_by('deficit')
    
    def despachar_por_lotes(self, *, cantidad, usuario, tipo_movimiento, pedido=None, detalle_transferencia=None, motivo=None):
        from django.db import transaction
        from django.db.models import F
        from django.core.exceptions import ValidationError
        from django.utils import timezone
        from .models import StockLote, MovimientoInventario, DetallePedido

        if int(cantidad) <= 0:
            raise ValidationError("La cantidad a despachar debe ser mayor a 0.")
        
        if pedido and pedido.estado_pedido.codigo in ['ANULADO', 'ENTREGADO', 'CANCELADO']:
            raise ValidationError(f"Pedido {pedido.codigo} no procesable.")

        movimientos_creados = []

        with transaction.atomic():
            inv = InventarioProducto.objects.select_for_update().get(pk=self.pk)
            
           
            if inv.stock_actual < int(cantidad):
                raise ValidationError(f"Stock insuficiente en {inv.bodega}. Físico: {inv.stock_actual}, Solicitado: {cantidad}")

           
            qs = self._qs_lotes_operativos()
        
            qs = self._ordenar_lotes_por_regla_producto(qs)

            restante = int(cantidad)
            for lote in qs:
                if restante <= 0: break

                tomar = min(lote.cantidad_disponible, restante)
                stock_inv_antes = inv.stock_actual
                StockLote.objects.filter(pk=lote.pk).update(
                    cantidad_disponible=F("cantidad_disponible") - tomar
                )
                lote.refresh_from_db()
                lote._auto_archivar_si_corresponde()
                
                inv.stock_actual -= tomar
                inv.fecha_ultimo_movimiento = timezone.now()
                inv.save()

                if pedido:
                    DetallePedido.objects.filter(pedido=pedido, producto=self.producto).update(
                        cantidad_atendida=F("cantidad_atendida") + tomar
                    )

            
                mov = MovimientoInventario.objects.create(
                    inventario=inv,
                    stock_lote=lote,
                    tipo_movimiento=tipo_movimiento,
                    pedido=pedido,
                    detalle_transferencia=detalle_transferencia,
                    bodega_origen=inv.bodega,
                    bodega_destino=detalle_transferencia.transferencia.bodega_destino if detalle_transferencia else None,
                    cantidad=tomar,
                    stock_antes=stock_inv_antes,
                    stock_despues=inv.stock_actual,
                    valor_unitario=lote.costo_compra_lote,
                    valor_total=tomar * lote.costo_compra_lote,
                    motivo=motivo or f"Salida Automática",
                    usuario=usuario
                )
                
                movimientos_creados.append(mov)
                restante -= tomar

            if restante > 0:
                raise ValidationError(
                    f"Discrepancia Logística: El sistema muestra {inv.stock_actual + restante} unidades, "
                    f"pero solo {int(cantidad) - restante} cumplen los criterios de calidad/caducidad/infraestructura."
                )

            if pedido:
                pedido.verificar_y_actualizar_estado()

        return movimientos_creados
        
class StockLote(models.Model):
    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name="lotes",
    )
    ubicacion = models.ForeignKey(
        UbicacionFisica,
        on_delete=models.PROTECT,
        related_name="lotes",
    )

    lote = models.CharField(max_length=120, blank=True, null=True)
    lote_proveedor = models.CharField(max_length=120, blank=True, null=True)

    cantidad_disponible = models.IntegerField(default=0)

    fecha_entrada = models.DateTimeField(default=timezone.now)
    fecha_caducidad = models.DateField(blank=True, null=True)
    costo_compra_lote = models.DecimalField(
        max_digits=18, 
        decimal_places=2, 
        default=0,
    )

    estado_lote = models.ForeignKey(
        EstadoLote,
        on_delete=models.PROTECT,
        related_name="lotes",
    )
    archivado = models.BooleanField(default=False)

    lote_origen = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lotes_derivados"
    )

    proveedor = models.ForeignKey(
        Proveedor,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="lotes"
    )

    class Meta:
        verbose_name = "Stock por lote"
        verbose_name_plural = "Stock por lote"
        constraints = [
            models.UniqueConstraint(
                fields=["producto", "lote", "ubicacion"],
                name="uq_lote_producto_ubicacion",
            ),
            models.CheckConstraint(
                condition=Q(cantidad_disponible__gte=0),
                name="ck_lote_cantidad_no_neg",
            ),
            
            models.CheckConstraint(
                condition=Q(costo_compra_lote__gte=0),
                name="ck_lote_costo_no_neg",
            ),
        ]
        indexes = [
            models.Index(fields=["producto", "estado_lote"]),
            models.Index(fields=["producto", "fecha_caducidad"]),
            models.Index(fields=["ubicacion"]),
            models.Index(fields=["lote"]),
            models.Index(fields=["archivado"]),
            models.Index(fields=["proveedor"]),
            models.Index(fields=["lote_origen"]),
        ]
    def obtener_arbol_genealogico(self) -> List[StockLote]:
        historial = [self]
        lote_actual = self
        while lote_actual.lote_origen:
            lote_actual = lote_actual.lote_origen
            historial.append(lote_actual)
        return historial

    @property
    def proveedor_original(self):
        genealogia = self.obtener_arbol_genealogico()
        return genealogia[-1].proveedor 
    def __str__(self):
        return f"{self.lote or 'SIN-LOTE'} - {self.producto.nombre}"
    @staticmethod
    def asignar_ubicacion_automatica(producto, bodega):
        
        qs = UbicacionFisica.objects.filter(
            es_activo=True,
            rack__es_activo=True,
            rack__zona__es_activo=True,
            rack__zona__bodega=bodega,
            rack__zona__tipo_almacenamiento=producto.tipo_almacenamiento
        )

        qs = qs.exclude(
            lotes__cantidad_disponible__gt=0
        )

        qs = qs.order_by(
            "rack__zona__codigo", 
            "rack__codigo", 
            "nivel_fila"
        )
        
        
        return qs.first()

    def _formatear_correlativo(self, n: int) -> str:
        return str(n).zfill(4) if n < 10000 else str(n)

    def _generar_siguiente_lote(self) -> str:
        bodega_id = "0"
        if self.ubicacion_id:
            bodega_id = str(self.ubicacion.rack.zona.bodega_id)
        elif hasattr(self, '_bodega_destino'):
            bodega_id = str(getattr(self._bodega_destino, 'id', self._bodega_destino))
        
        pref_bodega = f"B{bodega_id}"
        
        cat = (self.producto.categoria.prefijo_sku or self.producto.categoria.nombre)[:3].upper()
        mar = self.producto.marca.nombre[:3].upper()
        ori = "T" if self.lote_origen_id else "N" 
        cad = self.fecha_caducidad.strftime("%y%m%d") if self.fecha_caducidad else "000000"
        
        base = f"{pref_bodega}{cat}-{mar}-{ori}-{cad}-"
        
        ultimo = (
            StockLote.objects
            .filter(lote__startswith=base)
            .order_by("-lote")
            .first()
        )

        correlativo = 1
        if ultimo and ultimo.lote:
            try:
                correlativo = int(ultimo.lote.split("-")[-1]) + 1
            except (ValueError, IndexError):
                pass

        return f"{base}{str(correlativo).zfill(3)}"
    def _estado_por_marca(self, *, marca_disponible=False, marca_agotado=False, marca_vencido=False):
        qs = EstadoLote.objects.filter(es_activo=True)
        if marca_vencido:
            return qs.filter(marca_vencido=True).first()
        if marca_agotado:
            return qs.filter(marca_agotado=True).first()
        if marca_disponible:
            return qs.filter(marca_disponible=True).first()
        return None

       
    def es_vendible_por_fecha(self, hoy=None) -> bool:
        perfil = self.producto.perfil_caducidad
        if not perfil or not perfil.requiere_caducidad:
            return True
        if not self.fecha_caducidad:
            return False
        
        hoy = hoy or timezone.localdate()
        
        fecha_bloqueo = self.fecha_caducidad - timedelta(days=perfil.dias_bloqueo_previo)
        return hoy <= fecha_bloqueo 
    
            
    def es_vendible(self) -> bool:
        if self.archivado:
            return False
        if self.estado_lote and not self.estado_lote.es_vendible:
            return False
        return self.es_vendible_por_fecha()

    def _aplicar_politica_estado(self):
        if self.estado_lote and (self.estado_lote.marca_bloqueado or not self.estado_lote.es_vendible):
            return

        if not self.es_vendible_por_fecha():
            est = self._estado_por_marca(marca_vencido=True)
            if est:
                self.estado_lote = est
            return

        if (self.cantidad_disponible or 0) <= 0:
            est = self._estado_por_marca(marca_agotado=True)
            if est:
                self.estado_lote = est
            return

        est = self._estado_por_marca(marca_disponible=True)
        if est:
            self.estado_lote = est

    def asegurar_estado_actual(self, *, guardar=True) -> bool:
        estado_original_id = self.estado_lote_id
        self._aplicar_politica_estado()
        cambio = self.estado_lote_id != estado_original_id
        if cambio and guardar and self.pk:
            StockLote.objects.filter(pk=self.pk).update(estado_lote=self.estado_lote)
        return cambio

    def _auto_archivar_si_corresponde(self):
        if (self.cantidad_disponible or 0) <= 0:
            self.archivado = True
            return
        if not self.es_vendible():
            self.archivado = True

    @staticmethod
    def registrar_recepcion_transferencia(detalle_lote_trf, usuario):
        lote_original = detalle_lote_trf.stock_lote_origen
        bodega_dest = detalle_lote_trf.ubicacion_destino.rack.zona.bodega
        with transaction.atomic():
            nuevo_lote_dest = StockLote(
                producto=lote_original.producto,
                lote=lote_original.lote,  
                lote_proveedor=lote_original.lote_proveedor,
                fecha_caducidad=lote_original.fecha_caducidad,
                cantidad_disponible=detalle_lote_trf.cantidad,
                costo_compra_lote=lote_original.costo_compra_lote,
                estado_lote=lote_original.estado_lote, 
                lote_origen=lote_original, 
                proveedor=lote_original.proveedor,
            )
            nuevo_lote_dest._bodega_destino = bodega_dest 
            nuevo_lote_dest.save()
            detalle_lote_trf.stock_lote_destino = nuevo_lote_dest
            detalle_lote_trf.save()
    
    def clean(self):
       
        if not self.producto_id:
            raise ValidationError("Debe asignar un producto antes de registrar el lote.")
        if not self.ubicacion_id:
            raise ValidationError("Debe asignar una ubicación física (rack/nivel) al lote.")

        if self.ubicacion_id:
           
            ocupante = StockLote.objects.filter(
                ubicacion=self.ubicacion,
                cantidad_disponible__gt=0
            ).exclude(pk=self.pk).first()

            if ocupante:
                
                raise ValidationError(
                    f" UBICACIÓN OCUPADA: La celda {self.ubicacion.codigo_celda} ya contiene el lote '{ocupante.lote}' "
                    f"({ocupante.cantidad_disponible} un.). "
                    "Política FEFO Estricta: No se permite mezclar lotes en la misma celda. "
                    "Vacíe la celda o elija otra ubicación."
                )

        
        rack = self.ubicacion.rack
        zona = rack.zona
        bodega = zona.bodega
        
        if not bodega.es_activo:
            raise ValidationError(f"ERROR CRÍTICO: La bodega '{bodega.nombre}' está CLAUSURADA/INACTIVA.")
        if not zona.es_activo:
            raise ValidationError(f"La zona '{zona.nombre}' se encuentra inactiva.")
        if not rack.es_activo:
            raise ValidationError(f"El rack '{rack.codigo}' está inactivo.")
        if not self.ubicacion.es_activo:
            raise ValidationError(f"La ubicación '{self.ubicacion.codigo_celda}' está inactiva.")

      
        if self.producto_id:
            tipo_zona_id = zona.tipo_almacenamiento_id
            if self.producto.tipo_almacenamiento_id and tipo_zona_id != self.producto.tipo_almacenamiento_id:
                raise ValidationError(
                    f"Incompatibilidad: El producto requiere zona '{self.producto.tipo_almacenamiento}' "
                    f"pero intenta guardarlo en zona '{zona.tipo_almacenamiento}'."
                )

       
        faltantes = []
        
       
        if not EstadoLote.objects.filter(es_activo=True, marca_disponible=True).exists():
            faltantes.append("marca_disponible=True")
        if not EstadoLote.objects.filter(es_activo=True, marca_agotado=True).exists():
            faltantes.append("marca_agotado=True")

        
        perfil = self.producto.perfil_caducidad
        if perfil and perfil.requiere_caducidad:
            
            if not EstadoLote.objects.filter(es_activo=True, marca_vencido=True).exists():
                faltantes.append("marca_vencido=True")
            
           
            if not self.fecha_caducidad:
                raise ValidationError(f"El producto '{self.producto.nombre}' requiere fecha de caducidad obligatoria (Según Perfil: {perfil.codigo}).")

       
        if faltantes:
            raise ValidationError("Faltan EstadosLote parametrizados en el sistema: " + ", ".join(faltantes))

       
        if not self.estado_lote_id:
            raise ValidationError("Debe asignar un EstadoLote al lote (parametrización).")

        
        super().clean()


    def save(self, *args, **kwargs):
        
        if isinstance(self.lote, str):
            self.lote = self.lote.strip().upper() or None
        if isinstance(self.lote_proveedor, str):
            self.lote_proveedor = self.lote_proveedor.strip() or None
        
        
        if not self.pk and (self.costo_compra_lote is None or self.costo_compra_lote == 0):
             self.costo_compra_lote = self.producto.costo_compra
        if self.costo_compra_lote:
            self.costo_compra_lote = Decimal(str(self.costo_compra_lote)).quantize(Decimal('0.01'))
            
        
        if not self.lote:
            self.lote = self._generar_siguiente_lote()
        
        self._aplicar_politica_estado()
        self._auto_archivar_si_corresponde()


        if self.ubicacion_id and self.cantidad_disponible > 0:
            esta_ocupada = StockLote.objects.filter(
                ubicacion_id=self.ubicacion_id,
                cantidad_disponible__gt=0
            ).exclude(pk=self.pk).exists()
            
            if esta_ocupada:
                self._bodega_destino = self.ubicacion.rack.zona.bodega
                self.ubicacion = None 

       
        if not self.ubicacion_id and hasattr(self, '_bodega_destino'):
            auto_ubicacion = self.asignar_ubicacion_automatica(self.producto, self._bodega_destino)
            if auto_ubicacion:
                self.ubicacion = auto_ubicacion
            else:
                raise ValidationError(f"No hay espacio libre en {self._bodega_destino} para este tipo de producto.")

      
        if not self.archivado and self.cantidad_disponible > 0:
             self.full_clean() 

        super().save(*args, **kwargs)


class Cliente(models.Model):
    codigo = models.CharField(max_length=20, unique=True, null=True, blank=True)
    tipo_cliente = models.ForeignKey(TipoCliente, on_delete=models.PROTECT, related_name="clientes")

    tipo_identificacion = models.ForeignKey(
        TipoIdentificacion, on_delete=models.PROTECT, related_name="clientes", blank=True, null=True
    )
    numero_identificacion = models.CharField(max_length=30, blank=True, null=True)

    nombres = models.CharField(max_length=150, blank=True, null=True)
    apellidos = models.CharField(max_length=150, blank=True, null=True)
    correo = models.EmailField(max_length=150, blank=True, null=True)
    telefono = models.CharField(max_length=50, blank=True, null=True)
    direccion = models.CharField(max_length=300, blank=True, null=True)

    pais = models.ForeignKey(Pais, on_delete=models.PROTECT, related_name="clientes", blank=True, null=True)

    es_activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        constraints = [
            models.UniqueConstraint(
                Lower("numero_identificacion"),
                name="unique_cliente_ident_ci",
                condition=Q(numero_identificacion__isnull=False) & ~Q(numero_identificacion=""),
            )
        ]
        indexes = [
            models.Index(fields=["codigo"]),
            models.Index(fields=["es_activo"]),
            models.Index(fields=["numero_identificacion"]),
        ]

    def __str__(self):
        nom = " ".join([p for p in [self.nombres, self.apellidos] if p]) or "Cliente"
        return f"{self.codigo} | {nom}"

    def _generar_codigo(self) -> str:
        
        pais_iso = self.pais.codigo_iso[:2].upper() if self.pais else "XX"
        tipo_sigla = self.tipo_cliente.codigo[:3].upper() if self.tipo_cliente else "GEN"
        base = f"CLI-{pais_iso}-{tipo_sigla}-"
        
        ultimo = Cliente.objects.filter(codigo__startswith=base).order_by("-codigo").first()
        correlativo = 1
        if ultimo:
            try:
                correlativo = int(ultimo.codigo.split("-")[-1]) + 1
            except (ValueError, IndexError):
                correlativo = 1
        return f"{base}{str(correlativo).zfill(4)}"

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = self._generar_codigo()
        
        if isinstance(self.numero_identificacion, str):
            self.numero_identificacion = self.numero_identificacion.strip() or None
        if isinstance(self.nombres, str):
            self.nombres = self.nombres.strip().title() or None
        if isinstance(self.apellidos, str):
            self.apellidos = self.apellidos.strip().title() or None
        
        super().save(*args, **kwargs)


class Pedido(models.Model):
    class OrigenPedido(models.TextChoices):
        ERP = 'ERP', 'Venta Interna / Mostrador'
        WEB = 'WEB', 'E-commerce Online'

    origen = models.CharField(
        max_length=10,
        choices=OrigenPedido.choices,
        default=OrigenPedido.ERP,
        verbose_name="Canal de Venta"
    )
    codigo = models.CharField(max_length=30, unique=True, editable=False)
    
    pedido_padre = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="pedidos_derivados"
    )
    
    bodega_origen = models.ForeignKey(
        'Bodega', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='pedidos_origen',
        verbose_name="Bodega de Salida Predefinida"
    )
    
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="pedidos")
    estado_pedido = models.ForeignKey(EstadoPedido, on_delete=models.PROTECT, related_name="pedidos")
    
   
    usuario = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name="pedidos",
        null=True,   
        blank=True  
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)
   
    fecha_entrega = models.DateTimeField(
        null=True, 
        blank=True, 
        verbose_name="Fecha de Entrega Real"
    )
    observaciones = models.CharField(max_length=500, blank=True, null=True)

   
    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    monto_iva = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_costo = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    ganancia_total = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"
        constraints = [
            models.UniqueConstraint(Lower("codigo"), name="unique_pedido_codigo_ci"),
            models.CheckConstraint(condition=Q(total__gte=0), name="ck_pedido_total_no_neg"),
            models.CheckConstraint(condition=Q(total_costo__gte=0), name="ck_pedido_costo_no_neg"),
        ]
        indexes = [
            models.Index(fields=["codigo"]),
            models.Index(fields=["estado_pedido", "fecha_creacion"]),
            models.Index(fields=["usuario", "fecha_creacion"]),
        ]

    
    @property
    def porcentaje_completado(self):
       
        return self.calcular_porcentaje_avance()

    @property
    def esta_cerrado(self):
       
        return self.estado_pedido.codigo == EstadoPedido.CODIGO_ENTREGADO

   
    def procesar_despacho_completo(self, usuario):
        
        from .models import InventarioProducto, TipoMovimiento, EstadoPedido
        from django.db import transaction
        from django.core.exceptions import ValidationError

        try:
            with transaction.atomic():
                
                pedido_lock = Pedido.objects.select_for_update().get(pk=self.pk)
            
                estados_validos = [
                    EstadoPedido.CODIGO_SOLICITADO, 
                    EstadoPedido.CODIGO_PREPARACION,
                    getattr(EstadoPedido, 'CODIGO_PARCIAL', 'ENTREGA_PARCIAL'),
                    getattr(EstadoPedido, 'CODIGO_BACKORDER', 'BACKORDER')
                ]
                
                if pedido_lock.estado_pedido.codigo not in estados_validos:
                    raise ValidationError(f"El pedido {self.codigo} no es procesable en estado {self.estado_pedido.codigo}.")
                tm_venta, _ = TipoMovimiento.objects.get_or_create(
                    codigo=TipoMovimiento.CODIGO_VENTA,  
                    defaults={
                        'descripcion': 'Salida Automática Inteligente (Omnicanal)',
                        'es_entrada': False, 'es_salida': True, 'afecta_stock': True, 'es_activo': True
                    }
                )

                despachado_en_esta_sesion = False

               
                for detalle in pedido_lock.detalles.select_related('producto').all():
                    
                    pendiente_total = detalle.cantidad_solicitada - detalle.cantidad_atendida
                    
                    if pendiente_total <= 0:
                        continue 

                    inventarios_con_stock = InventarioProducto.objects.select_for_update().filter(
                        producto=detalle.producto,
                        stock_actual__gt=0,
                        bodega__es_activo=True
                    ).order_by('-stock_actual')

                    for inv in inventarios_con_stock:
                        if pendiente_total <= 0:
                            break
                        
                        
                        cantidad_a_tomar = min(pendiente_total, inv.stock_actual)

                        inv.despachar_por_lotes(
                            cantidad=cantidad_a_tomar,
                            usuario=usuario,
                            tipo_movimiento=tm_venta,
                            pedido=self,
                            motivo=f"Despacho automático inteligente desde {inv.bodega.nombre}"
                        )
                        
                        pendiente_total -= cantidad_a_tomar
                        despachado_en_esta_sesion = True

                
                if not despachado_en_esta_sesion:
                    raise ValidationError("No se encontró stock disponible en ninguna bodega para procesar este pedido.")

               
                self.verificar_y_actualizar_estado()
                return True

        except Exception as e:
            raise e
    

    def simular_plan_despacho(self):
        from .models import StockLote
        plan = []
        
        for detalle in self.detalles.all():
            pendiente = detalle.cantidad_solicitada - detalle.cantidad_atendida
            if pendiente <= 0: continue
                
            es_perecedero = detalle.producto.perfil_caducidad and detalle.producto.perfil_caducidad.requiere_caducidad
            criterio_orden = 'fecha_caducidad' if es_perecedero else 'fecha_entrada'
            
            lotes_compatibles = StockLote.objects.filter(
                producto=detalle.producto,
                cantidad_disponible__gt=0,
                estado_lote__es_vendible=True
            ).select_related('ubicacion__rack__zona__bodega').order_by(criterio_orden)
            
            lotes_detalle = []
            cantidad_localizada = 0
            
            for lote in lotes_compatibles:
                if cantidad_localizada >= pendiente: break
                
                tomar = min(lote.cantidad_disponible, pendiente - cantidad_localizada)
                ubi = lote.ubicacion
                
                lotes_detalle.append({
                    'id_bodega': ubi.rack.zona.bodega.id,
                    'bodega_nombre': ubi.rack.zona.bodega.nombre,
                    'zona_codigo': ubi.rack.zona.codigo,
                    'rack_codigo': ubi.rack.codigo,
                    'nivel': ubi.nivel_fila,  
                    'celda': ubi.codigo_celda,
                    'lote_codigo': lote.lote,
                    'cantidad': tomar,
                    'vencimiento': lote.fecha_caducidad
                })
                cantidad_localizada += tomar
                
            plan.append({
                'producto': detalle.producto.nombre,
                'cantidad_pendiente': pendiente,
                'lotes': lotes_detalle, 
                'completo': cantidad_localizada >= pendiente
            })
        return plan
    def autorizar_salida_fraccionada(self, usuario, bodega):
        
        from .models import InventarioProducto, TipoMovimiento
        
        pedido_lock = Pedido.objects.select_for_update().get(pk=self.pk)
        tm_venta = TipoMovimiento.objects.get(codigo=TipoMovimiento.CODIGO_VENTA)
        
        se_movio_algo = False

        for detalle in pedido_lock.detalles.all():
            pendiente = detalle.cantidad_solicitada - detalle.cantidad_atendida
            if pendiente <= 0:
                continue
                
           
            inv = InventarioProducto.objects.filter(
                producto=detalle.producto,
                bodega=bodega,
                stock_actual__gt=0
            ).first()

            if inv:
                cantidad_a_despachar = min(pendiente, inv.stock_actual)
                
               
                inv.despachar_por_lotes(
                    cantidad=cantidad_a_despachar,
                    usuario=usuario,
                    tipo_movimiento=tm_venta,
                    pedido=self,
                    motivo=f"Salida autorizada por bodeguero en {bodega.nombre}"
                )
                se_movio_algo = True

        if se_movio_algo:
            self.verificar_y_actualizar_estado()
            
        return se_movio_algo
    def verificar_y_actualizar_estado(self):
        
        detalles = self.detalles.all()
        if not detalles.exists(): return

        total_solicitado = sum(d.cantidad_solicitada for d in detalles)
        total_atendido = sum(d.cantidad_atendida for d in detalles)

        nuevo_estado = None
        campos_a_actualizar = ['estado_pedido']

        
        if total_atendido >= total_solicitado and total_solicitado > 0:
            nuevo_estado = EstadoPedido.objects.filter(codigo=EstadoPedido.CODIGO_ENTREGADO).first()
            if not self.fecha_entrega:
                self.fecha_entrega = timezone.now()
                campos_a_actualizar.append('fecha_entrega')
            
        
        elif 0 < total_atendido < total_solicitado:
            nuevo_estado, _ = EstadoPedido.objects.get_or_create(
                codigo=getattr(EstadoPedido, 'CODIGO_PARCIAL', 'ENTREGA_PARCIAL'),
                defaults={'descripcion': 'Entrega parcial en progreso', 'es_activo': True}
            )

        if nuevo_estado and self.estado_pedido != nuevo_estado:
            self.estado_pedido = nuevo_estado
            self.save(update_fields=campos_a_actualizar)

    def _generar_siguiente_codigo(self) -> str:
        hoy = timezone.localdate().strftime('%Y%m%d')
        prefijo_bodega = "B00" 
        
        if self.origen == self.OrigenPedido.WEB:
            prefijo_bodega = "BWEB"
        else:
            perfil = getattr(self.usuario, 'perfil', None)
            if perfil and perfil.bodega:
                prefijo_bodega = f"B{str(perfil.bodega.id).zfill(2)}"
            
        base = f"PED-{prefijo_bodega}-{hoy}-"
        ultimo = Pedido.objects.filter(codigo__startswith=base).order_by("-codigo").first()
        correlativo = 1
        if ultimo:
            try:
                correlativo = int(ultimo.codigo.split("-")[-1]) + 1
            except (ValueError, IndexError): pass
        return f"{base}{str(correlativo).zfill(4)}"

    def recalcular_totales(self):
        res = self.detalles.aggregate(
            sum_subtotal=Coalesce(Sum('subtotal'), Value(Decimal("0.00"))),
            sum_impuesto=Coalesce(Sum('valor_impuesto'), Value(Decimal("0.00"))),
            sum_total=Coalesce(Sum('total_linea'), Value(Decimal("0.00"))),
            sum_costo=Coalesce(Sum('subtotal_costo'), Value(Decimal("0.00"))),
            sum_ganancia=Coalesce(Sum('ganancia'), Value(Decimal("0.00")))
        )
        self.subtotal, self.monto_iva, self.total = res['sum_subtotal'], res['sum_impuesto'], res['sum_total']
        self.total_costo, self.ganancia_total = res['sum_costo'], res['sum_ganancia']
        self.save(update_fields=["subtotal", "monto_iva", "total", "total_costo", "ganancia_total"])

    def calcular_porcentaje_avance(self):
        det = self.detalles.all()
        if not det: return 0
        total_sol = sum(d.cantidad_solicitada for d in det)
        total_ate = sum(d.cantidad_atendida for d in det)
        return int((total_ate / total_sol) * 100) if total_sol > 0 else 0

    def __str__(self):
        return f"{self.codigo} ({self.estado_pedido})"

    def save(self, *args, **kwargs):
        if self.observaciones: self.observaciones = self.observaciones.strip()
        if not self.codigo: self.codigo = self._generar_siguiente_codigo()
        
        
        if self.origen == self.OrigenPedido.WEB and not self.estado_pedido_id:
            estado_ini = EstadoPedido.objects.filter(codigo=EstadoPedido.CODIGO_SOLICITADO).first()
            if estado_ini: self.estado_pedido = estado_ini

        for i in range(5):
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                if i == 4: raise
                self.codigo = self._generar_siguiente_codigo()
class DetallePedido(models.Model):
    class EstadoLogistico(models.TextChoices):
        DISPONIBLE = "DISPONIBLE", "Listo para despacho"
        ESPERANDO_TRASPASO = "ESPERANDO_TRASPASO", "Stock faltante (Requiere Traspaso)"
        EN_TRANSITO = "EN_TRANSITO", "En camino desde otra bodega"
        ATENDIDO = "ATENDIDO", "Entregado totalmente"

    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name="detalles")
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name="detalles_pedido")
    cantidad_solicitada = models.IntegerField()
    cantidad_atendida = models.IntegerField(default=0)
    
    estado_logistico = models.CharField(
        max_length=20,
        choices=EstadoLogistico.choices,
        default=EstadoLogistico.DISPONIBLE
    )

    precio_unitario = models.DecimalField(max_digits=18, decimal_places=2)
    costo_unitario = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    porcentaje_iva = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    valor_impuesto = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_linea = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    subtotal_costo = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    ganancia = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        
        if not self.precio_unitario:
            self.precio_unitario = self.producto.precio_venta
        if not self.costo_unitario or self.costo_unitario == 0:
            self.costo_unitario = self.producto.costo_compra
        if (not self.porcentaje_iva or self.porcentaje_iva == 0) and self.producto.impuesto:
            self.porcentaje_iva = self.producto.impuesto.porcentaje

        
        self.precio_unitario = Decimal(str(self.precio_unitario)).quantize(Decimal('0.01'))
        self.costo_unitario = Decimal(str(self.costo_unitario)).quantize(Decimal('0.01'))
        cant_dec = Decimal(str(self.cantidad_solicitada))
        
        self.subtotal = (cant_dec * self.precio_unitario).quantize(Decimal('0.01'))
        self.valor_impuesto = (self.subtotal * (self.porcentaje_iva / 100)).quantize(Decimal('0.01'))
        self.total_linea = self.subtotal + self.valor_impuesto
        self.subtotal_costo = (cant_dec * self.costo_unitario).quantize(Decimal('0.01'))
        self.ganancia = self.subtotal - self.subtotal_costo

        
        if self.cantidad_atendida >= self.cantidad_solicitada:
            self.estado_logistico = self.EstadoLogistico.ATENDIDO
        else:
            from .models import InventarioProducto
            
            pendiente = self.cantidad_solicitada - self.cantidad_atendida
 
            perfil_vendedor = getattr(self.pedido.usuario, 'perfil', None) if self.pedido.usuario else None
            
            if perfil_vendedor and perfil_vendedor.bodega:
                inv = InventarioProducto.objects.filter(
                    producto=self.producto, 
                    bodega=perfil_vendedor.bodega
                ).first()
                stock_disponible = inv.stock_actual if inv else 0
            else:
                stock_disponible = InventarioProducto.objects.filter(
                    producto=self.producto
                ).aggregate(total=Sum('stock_actual'))['total'] or 0

            if stock_disponible < pendiente:
                self.estado_logistico = self.EstadoLogistico.ESPERANDO_TRASPASO
            else:
                self.estado_logistico = self.EstadoLogistico.DISPONIBLE


        super().save(*args, **kwargs)

 
        if self.pedido:
           
            self.pedido.recalcular_totales()
            
            self.pedido.verificar_y_actualizar_estado()

class MovimientoInventario(models.Model):
    codigo = models.CharField(max_length=30, unique=True, editable=False)
    inventario = models.ForeignKey(
        "InventarioProducto",
        on_delete=models.CASCADE,
        related_name="movimientos",
    )
    stock_lote = models.ForeignKey(
        "StockLote",
        on_delete=models.PROTECT,
        related_name="movimientos",
    )
    tipo_movimiento = models.ForeignKey(
        "TipoMovimiento",
        on_delete=models.PROTECT,
        related_name="movimientos",
    )
    usuario = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="movimientos_inventario",
    )
    pedido = models.ForeignKey(
        "Pedido",
        on_delete=models.SET_NULL,
        related_name="movimientos_inventario",
        blank=True,
        null=True,
    )
    detalle_transferencia = models.ForeignKey(
        "DetalleTransferenciaLote",
        on_delete=models.PROTECT,
        related_name="movimientos",
        null=True,
        blank=True
    )
    bodega_origen = models.ForeignKey(
        "Bodega",
        on_delete=models.SET_NULL,
        related_name="movimientos_salida",
        blank=True,
        null=True,
    )
    bodega_destino = models.ForeignKey(
        "Bodega",
        on_delete=models.SET_NULL,
        related_name="movimientos_entrada",
        blank=True,
        null=True,
    )
    fecha = models.DateTimeField(default=timezone.now)
    cantidad = models.IntegerField()
    stock_antes = models.IntegerField(blank=True, null=True)
    stock_despues = models.IntegerField(blank=True, null=True)
    
    valor_unitario = models.DecimalField(
        max_digits=18, 
        decimal_places=2, 
        default=0
    )
    
    valor_total = models.DecimalField(
        max_digits=18, 
        decimal_places=2, 
        default=0
    )

    motivo = models.CharField(max_length=300, blank=True, null=True)

    class Meta:
        verbose_name = "Movimiento de inventario"
        verbose_name_plural = "Movimientos de inventario"
        constraints = [
            models.UniqueConstraint(Lower("codigo"), name="unique_movimiento_codigo_ci"),
            models.CheckConstraint(condition=Q(cantidad__gt=0), name="ck_mov_cantidad_gt0"),
            models.CheckConstraint(
                condition=~(Q(pedido__isnull=False) & Q(detalle_transferencia__isnull=False)),
                name="ck_mov_no_pedido_y_transferencia_a_la_vez",
            ),
            models.CheckConstraint(
                condition=(
                    Q(detalle_transferencia__isnull=True)
                    | (Q(bodega_origen__isnull=False) & Q(bodega_destino__isnull=False))
                ),
                name="ck_mov_transferencia_requiere_bodegas",
            ),
            models.CheckConstraint(
                condition=(
                    Q(detalle_transferencia__isnull=True)
                    | ~Q(bodega_origen=F("bodega_destino"))
                ),
                name="ck_mov_transferencia_origen_destino_distintos",
            ),
            models.CheckConstraint(
                condition=(Q(stock_antes__isnull=True) | Q(stock_antes__gte=0)),
                name="ck_mov_stock_antes_no_neg",
            ),
            models.CheckConstraint(
                condition=(Q(stock_despues__isnull=True) | Q(stock_despues__gte=0)),
                name="ck_mov_stock_despues_no_neg",
            ),
        ]
        indexes = [
            models.Index(fields=["codigo"]),
            models.Index(fields=["fecha"]),
            models.Index(fields=["tipo_movimiento", "fecha"]),
            models.Index(fields=["inventario", "fecha"]),
            models.Index(fields=["pedido"]),
            models.Index(fields=["detalle_transferencia"]),
            models.Index(fields=["usuario", "fecha"]),
            models.Index(fields=["bodega_origen", "fecha"]),
            models.Index(fields=["bodega_destino", "fecha"]),
        ]

    def __str__(self):
        return f"{self.codigo} - {self.tipo_movimiento.codigo} (Lote: {self.stock_lote.lote})"

    def _generar_siguiente_codigo(self) -> str:
        hoy = timezone.localdate().strftime('%y%m%d')
        if self.pedido_id:
            prefijo = "VTA"  
        elif self.detalle_transferencia_id:
            prefijo = "TRF"  
        else:
            prefijo = "MOV"  
        b_id = str(self.inventario.bodega_id).zfill(2)
        base = f"{prefijo}-{b_id}-{hoy}-"

        ultimo = MovimientoInventario.objects.filter(codigo__startswith=base).order_by("-codigo").first()
        correlativo = 1
        if ultimo:
            try:
                correlativo = int(ultimo.codigo.split("-")[-1]) + 1
            except: pass

        return f"{base}{str(correlativo).zfill(4)}"
    @property
    def valor_patrimonial_momento(self):
    
        if self.stock_despues is not None:
            return self.stock_despues * self.valor_unitario
        return Decimal("0.00")
    def clean(self):
        if isinstance(self.motivo, str):
            self.motivo = self.motivo.strip() or None
        
       
        if self.detalle_transferencia_id:
            tr_header = self.detalle_transferencia.detalle.transferencia
            if self.bodega_origen_id and self.bodega_origen_id != tr_header.bodega_origen_id:
                raise ValidationError("La bodega_origen no coincide con el documento de transferencia.")
            if self.bodega_destino_id and self.bodega_destino_id != tr_header.bodega_destino_id:
                raise ValidationError("La bodega_destino no coincide con el documento de transferencia.")
        
       
        if self.stock_lote and self.inventario:
            bodega_lote = self.stock_lote.ubicacion.rack.zona.bodega
            if bodega_lote != self.inventario.bodega:
                raise ValidationError(
                    f"Conflicto físico: El lote {self.stock_lote.lote} pertenece a la "
                    f"bodega {bodega_lote}, pero se intenta mover en {self.inventario.bodega}."
                )
        super().clean()

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = self._generar_siguiente_codigo()
        
      
        if not self.pk:
            self.valor_unitario = self.stock_lote.costo_compra_lote
            self.valor_total = Decimal(str(self.cantidad)) * self.valor_unitario

        
        if self.stock_antes is not None and self.stock_despues is not None:
            operador = 1 if self.tipo_movimiento.es_entrada else -1
            esperado = self.stock_antes + (self.cantidad * operador)
            if self.stock_despues != esperado:
                raise ValidationError(f"Error de integridad: El stock después ({self.stock_despues}) "
                                    f"no coincide con el cálculo esperado ({esperado}).")
        
        with transaction.atomic():
            super().save(*args, **kwargs)
            lote = self.stock_lote
            lote.refresh_from_db()
            lote._auto_archivar_si_corresponde()
            lote.save(update_fields=['archivado'])
    
class TransferenciaInterna(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = "BORRADOR", "Borrador"
        SOLICITADA = "SOLICITADA", "Solicitada"
        EN_PREPARACION = "EN_PREPARACION", "En preparación"
        DESPACHADA = "DESPACHADA", "Despachada"
        RECIBIDA = "RECIBIDA", "Recibida"
        CANCELADA = "CANCELADA", "Cancelada"

    class Tipo(models.TextChoices):
        POR_PEDIDO = "POR_PEDIDO", "Por pedido"
        CONTINGENCIA = "CONTINGENCIA", "Contingencia"
        REABASTECIMIENTO = "REABASTECIMIENTO", "Reabastecimiento"
        MANUAL = 'MANUAL', 'Reabastecimiento Manual (Push)'
    tipo = models.CharField(
        max_length=20,
        choices=Tipo.choices,
        default=Tipo.POR_PEDIDO,
        db_index=True,
    )

    
    pedido = models.ForeignKey(
        "Pedido",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transferencias_internas",
    )

    codigo = models.CharField(max_length=30, unique=True, editable=False)

    bodega_origen = models.ForeignKey(
        "Bodega",
        on_delete=models.PROTECT,
        related_name="transferencias_salida",
    )
    bodega_destino = models.ForeignKey(
        "Bodega",
        on_delete=models.PROTECT,
        related_name="transferencias_entrada",
    )

    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.BORRADOR,
        db_index=True,
    )

    usuario_solicita = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name="solicitudes_transferencia"
    )
    usuario_ejecuta = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        null=True, blank=True,
        related_name="ejecuciones_transferencia"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    fecha_cierre = models.DateTimeField(null=True, blank=True) 
    observaciones = models.CharField(max_length=500, blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("codigo"), name="unique_transferencia_codigo_ci"),
            models.CheckConstraint(
                condition=~Q(bodega_origen=F("bodega_destino")),
                name="ck_transferencia_bodegas_distintas",
            ),

            
            models.CheckConstraint(
                condition=~(Q(tipo="POR_PEDIDO") & Q(pedido__isnull=True)),
                name="ck_transferencia_por_pedido_requiere_pedido",
            ),

            
            models.CheckConstraint(
                condition=~(Q(pedido__isnull=False) & ~Q(tipo="POR_PEDIDO")),
                name="ck_transferencia_si_hay_pedido_tipo_por_pedido",
            ),
        ]

    def obtener_valor_en_transito(self) -> Decimal:
        
        
        resultado = self.detalles.aggregate(
            valor_total=Sum(
               
                (F('lotes_asignados__cantidad') - Coalesce(F('lotes_asignados__stock_lote_destino__cantidad_disponible'), 0)) 
                * F('lotes_asignados__stock_lote_origen__costo_compra_lote'),
                output_field=models.DecimalField()
            )
        )
        
        valor = resultado.get('valor_total')
        return (valor or Decimal("0.00")).quantize(Decimal("0.01"))
    
    def despachar_transferencia(self, usuario_bodega):
       
        if self.estado != self.Estado.SOLICITADA and self.estado != self.Estado.EN_PREPARACION:
            raise ValidationError(f"No se puede despachar una transferencia en estado {self.estado}")
        
        self.estado = self.Estado.DESPACHADA
        self.usuario_ejecuta = usuario_bodega
        self.save(update_fields=['estado', 'usuario_ejecuta'])

    def ejecutar_despacho_fisico(self, usuario):
        
        from .models import (
            TipoMovimiento, InventarioProducto, StockLote, 
            UbicacionFisica, DetalleTransferenciaLote, MovimientoInventario
        )

        if self.estado not in [self.Estado.SOLICITADA, self.Estado.EN_PREPARACION]:
             raise ValidationError(f"No se puede despachar una transferencia en estado {self.estado}")
        
        tm_salida = TipoMovimiento.objects.filter(es_salida=True, codigo__icontains="TRF_SALIDA").first()
        if not tm_salida:
             tm_salida = TipoMovimiento.objects.filter(es_salida=True).first()

        with transaction.atomic():
            
            lotes_preasignados = DetalleTransferenciaLote.objects.filter(detalle__transferencia=self)
            
            if lotes_preasignados.exists():
               
                for linea_lote in lotes_preasignados:
                    lote = linea_lote.stock_lote_origen
                    cantidad = linea_lote.cantidad

                    if lote.cantidad_disponible < cantidad:
                        raise ValidationError(f"El lote {lote.lote} no tiene suficiente stock para despachar.")

                    inv_origen = InventarioProducto.objects.select_for_update().get(
                        producto=lote.producto, 
                        bodega=self.bodega_origen
                    )
                    
            
                    stock_antes = inv_origen.stock_actual
                    lote.cantidad_disponible -= cantidad
                    lote._auto_archivar_si_corresponde()
                    lote.save()
                    
                    inv_origen.stock_actual -= cantidad
                    inv_origen.save()

                    
                    MovimientoInventario.objects.create(
                        inventario=inv_origen,
                        stock_lote=lote,
                        tipo_movimiento=tm_salida,
                        usuario=usuario,
                        bodega_origen=self.bodega_origen,
                        bodega_destino=self.bodega_destino,
                        detalle_transferencia=linea_lote,
                        cantidad=cantidad,
                        stock_antes=stock_antes,
                        stock_despues=inv_origen.stock_actual,
                        valor_unitario=lote.costo_compra_lote,
                        valor_total=lote.costo_compra_lote * cantidad,
                        motivo=f"Salida Transferencia Manual {self.codigo}"
                    )

            else:
               
                for detalle in self.detalles.all():
                    cantidad_pendiente = detalle.cantidad_solicitada
                    inv_origen = InventarioProducto.objects.select_for_update().get(
                        producto=detalle.producto, bodega=self.bodega_origen
                    )
                    lotes_disponibles = inv_origen._qs_lotes_operativos()
                    lotes_disponibles = inv_origen._ordenar_lotes_por_regla_producto(lotes_disponibles)
                    
                    for lote in lotes_disponibles:
                        if cantidad_pendiente <= 0: break
                        tomar = min(lote.cantidad_disponible, cantidad_pendiente)
                        
                      
                        link_auditoria = DetalleTransferenciaLote.objects.create(
                            detalle=detalle,
                            stock_lote_origen=lote,
                            ubicacion_destino=UbicacionFisica.objects.filter(rack__zona__bodega=self.bodega_destino).first(),
                            cantidad=tomar
                        )

                
                        stock_antes = inv_origen.stock_actual
                        lote.cantidad_disponible -= tomar
                        lote._auto_archivar_si_corresponde()
                        lote.save()
                        inv_origen.stock_actual -= tomar
                        inv_origen.save()

                        MovimientoInventario.objects.create(
                            inventario=inv_origen,
                            stock_lote=lote,
                            tipo_movimiento=tm_salida,
                            usuario=usuario,
                            bodega_origen=self.bodega_origen,
                            bodega_destino=self.bodega_destino,
                            detalle_transferencia=link_auditoria,
                            cantidad=tomar,
                            stock_antes=stock_antes,
                            stock_despues=inv_origen.stock_actual,
                            valor_unitario=lote.costo_compra_lote,
                            valor_total=lote.costo_compra_lote * tomar,
                            motivo=f"Salida Transferencia {self.codigo}"
                        )
                        cantidad_pendiente -= tomar
                    
                    if cantidad_pendiente > 0:
                         raise ValidationError(f"Stock insuficiente para {detalle.producto.nombre}")

            
            self.estado = self.Estado.DESPACHADA
            self.usuario_ejecuta = usuario
            self.save()

    def actualizar_estado_recepcion(self):
        detalles = self.detalles.all()
        res = detalles.aggregate(
            solicitado=models.Sum('cantidad_solicitada'),
            atendido=models.Sum('cantidad_atendida')
        )
        
        total_solicitado = res['solicitado'] or 0
        total_atendido = res['atendido'] or 0
        
        if total_solicitado > 0 and total_atendido >= total_solicitado:
            self.estado = self.Estado.RECIBIDA
            self.fecha_cierre = timezone.now()
            self.save(update_fields=['estado', 'fecha_cierre'])

    def __str__(self):
        return f"{self.codigo} ({self.get_estado_display()})"

    def _formatear_correlativo(self, n: int) -> str:
        return str(n).zfill(4)

    def _generar_codigo(self) -> str:
        hoy = timezone.localdate().strftime('%y%m%d')
        prefijos = {
            "POR_PEDIDO": "PED",
            "CONTINGENCIA": "CON",
            "REABASTECIMIENTO": "REA"
        }
        pref = prefijos.get(self.tipo, "TRF")
        b_org = str(self.bodega_origen_id or 0).zfill(2)
        b_des = str(self.bodega_destino_id or 0).zfill(2)
        usr_id = str(self.usuario_solicita_id or 0).zfill(2)
        
        base = f"{pref}-{b_org}T{b_des}-{hoy}-{usr_id}-"
        
        ultimo = (
            TransferenciaInterna.objects.select_for_update()
            .filter(codigo__startswith=base)
            .order_by("-codigo")
            .first()
        )

        correlativo = 1
        if ultimo:
            try:
                partes = ultimo.codigo.split("-")
                correlativo = int(partes[-1]) + 1
            except (ValueError, IndexError):
                correlativo = 1

        return f"{base}{str(correlativo).zfill(3)}"

    def clean(self):
        if self.tipo == self.Tipo.POR_PEDIDO and self.pedido_id is None:
            raise ValidationError("Si la transferencia es POR_PEDIDO, debe estar asociada a un Pedido.")
        
        super().clean()

    def save(self, *args, **kwargs):
        
        if self.observaciones:
            self.observaciones = self.observaciones.strip()
        if not self.codigo:
            self.codigo = self._generar_codigo()
        self.full_clean()
        super().save(*args, **kwargs)

class DetalleTransferenciaInterna(models.Model):
    transferencia = models.ForeignKey(
        TransferenciaInterna,
        on_delete=models.CASCADE,
        related_name="detalles",
    )

    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name="detalles_transferencia",
    )

    
    cantidad_solicitada = models.IntegerField()
    
   
    cantidad_atendida = models.IntegerField(default=0)

    class Meta:
        verbose_name = "Detalle de transferencia"
        verbose_name_plural = "Detalles de transferencia"
        constraints = [
            models.UniqueConstraint(
                fields=["transferencia", "producto"],
                name="unique_detalle_transferencia_producto",
            ),
            models.CheckConstraint(
                condition=Q(cantidad_solicitada__gt=0),
                name="ck_transferencia_cant_solicitada_gt0",
            ),
            models.CheckConstraint(
                condition=Q(cantidad_atendida__gte=0),
                name="ck_transferencia_cant_atendida_gte0",
            ),
            
            models.CheckConstraint(
                condition=Q(cantidad_atendida__lte=F("cantidad_solicitada")),
                name="ck_transferencia_atendida_lte_solicitada",
            ),
        ]
        indexes = [
            models.Index(fields=["transferencia"]),
            models.Index(fields=["producto"]),
        ]

    def __str__(self):
        return f"{self.producto.nombre} (Sol: {self.cantidad_solicitada} | Ate: {self.cantidad_atendida})"

    @property
    def completado(self) -> bool:
        return self.cantidad_atendida >= self.cantidad_solicitada

    @property
    def porcentaje_progreso(self) -> float:
        if self.cantidad_solicitada == 0:
            return 0.0
        return round((self.cantidad_atendida / self.cantidad_solicitada) * 100, 2)

    def clean(self):
        
        if not self.producto_id:
            raise ValidationError("El detalle debe tener un producto asociado.")

        if self.cantidad_atendida > self.cantidad_solicitada:
            raise ValidationError({
                'cantidad_atendida': (
                    f"Error de integridad: Se intenta recibir {self.cantidad_atendida}, "
                    f"pero solo se solicitaron {self.cantidad_solicitada}."
                )
            })

        super().clean()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
class DetalleTransferenciaLote(models.Model):
    detalle = models.ForeignKey(
        DetalleTransferenciaInterna,
        on_delete=models.CASCADE,
        related_name="lotes_asignados",
    )

    stock_lote_origen = models.ForeignKey(
        "StockLote",
        on_delete=models.PROTECT,
        related_name="transferencias_lote_salida",
    )

    
    ubicacion_destino = models.ForeignKey(
        "UbicacionFisica",
        on_delete=models.PROTECT,
        related_name="transferencias_lote_entrada",
    )

    cantidad = models.PositiveIntegerField()

    stock_lote_destino = models.ForeignKey(
        "StockLote",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transferencias_lote_recibidas",
    )

    class Meta:
        verbose_name = "Detalle transferencia por lote"
        verbose_name_plural = "Detalles transferencia por lote"
        constraints = [
            models.CheckConstraint(condition=Q(cantidad__gt=0), name="ck_trf_lote_cantidad_gt0"),
        ]
        indexes = [
            models.Index(fields=["detalle"]),
            models.Index(fields=["stock_lote_origen"]),
            models.Index(fields=["ubicacion_destino"]),
        ]

    def __str__(self):
        return f"{self.detalle.producto.nombre} | {self.stock_lote_origen.lote} x {self.cantidad}"

    def clean(self):
        tr = self.detalle.transferencia
        if self.stock_lote_origen.producto_id != self.detalle.producto_id:
            raise ValidationError("El lote origen no corresponde al producto del detalle.")
        bodega_lote = self.stock_lote_origen.ubicacion.rack.zona.bodega
        if bodega_lote != tr.bodega_origen:
            raise ValidationError(
                f"Error Físico: El lote está en {bodega_lote}, pero la transferencia sale de {tr.bodega_origen}."
            )
        bodega_dest_plan = self.ubicacion_destino.rack.zona.bodega
        if bodega_dest_plan != tr.bodega_destino:
            raise ValidationError(
                f"Error Físico: La ubicación destino pertenece a {bodega_dest_plan}, no a {tr.bodega_destino}."
            )
        if not self.pk and self.cantidad > (self.stock_lote_origen.cantidad_disponible or 0):
            raise ValidationError(f"Stock insuficiente en el lote {self.stock_lote_origen.lote}.")


        ya_existe = DetalleTransferenciaLote.objects.filter(
            stock_lote_origen=self.stock_lote_origen,
            stock_lote_destino__isnull=True 
        ).exclude(pk=self.pk)

        if ya_existe.exists():
            raise ValidationError(f"STOP: El lote {self.stock_lote_origen.lote} ya está en tránsito en otra transferencia.")
            
        super().clean()

    def save(self, *args, **kwargs):
     
        self.full_clean()
        super().save(*args, **kwargs)

    def confirmar_recepcion_y_vincular_pedido(self, usuario):
        with transaction.atomic():
           
            nuevo_lote = self.confirmar_recepcion_automatica(usuario)

            pedido = self.detalle.transferencia.pedido
            
          
            if pedido and pedido.estado_pedido.codigo not in ['CERRADO', 'ANULADO']:
                inv_producto = InventarioProducto.objects.select_for_update().get(
                    producto=self.detalle.producto, 
                    bodega=usuario.perfil.bodega
                )

                t_mov = TipoMovimiento.objects.filter(codigo="VENTA").first() 
                
               
                inv_producto.despachar_por_lotes(
                    cantidad=self.cantidad,
                    usuario=usuario,
                    tipo_movimiento=t_mov,
                    pedido=pedido,
                    motivo=f"Despacho Cross-Docking desde TRF: {self.detalle.transferencia.codigo}"
                )
        return nuevo_lote

    def confirmar_recepcion_automatica(self, usuario):
        
        
        if self.stock_lote_destino:
            return self.stock_lote_destino 

        bodega_destino = self.detalle.transferencia.bodega_destino
        
      
        if hasattr(usuario, 'perfil') and usuario.perfil.bodega and usuario.perfil.bodega != bodega_destino:
             pass 

        with transaction.atomic():
            
            locked_self = DetalleTransferenciaLote.objects.select_for_update().get(pk=self.pk)
            
            if locked_self.stock_lote_destino:
                return locked_self.stock_lote_destino

            
            estado_vendible = EstadoLote.objects.filter(
                models.Q(marca_disponible=True) | models.Q(codigo='DISPONIBLE'),
                es_vendible=True,
                es_activo=True
            ).order_by('-marca_disponible').first()

            if not estado_vendible:
                estado_vendible, _ = EstadoLote.objects.get_or_create(
                    codigo='DISPONIBLE',
                    defaults={
                        'descripcion': 'Disponible para Venta',
                        'es_vendible': True,
                        'marca_disponible': True,
                        'es_activo': True
                    }
                )

           
            nuevo_lote = StockLote(
                producto=self.stock_lote_origen.producto,
                lote=self.stock_lote_origen.lote,
                lote_proveedor=self.stock_lote_origen.lote_proveedor,
                fecha_caducidad=self.stock_lote_origen.fecha_caducidad,
                cantidad_disponible=self.cantidad,
                costo_compra_lote=self.stock_lote_origen.costo_compra_lote,
                estado_lote=estado_vendible, 
                lote_origen=self.stock_lote_origen,
                proveedor=self.stock_lote_origen.proveedor,
            )
            
            
            if self.ubicacion_destino:
                nuevo_lote.ubicacion = self.ubicacion_destino 
            else:
                nuevo_lote._bodega_destino = bodega_destino 
            
            nuevo_lote.save()
            
            
            inv_destino, _ = InventarioProducto.objects.get_or_create(
                producto=self.detalle.producto, bodega=bodega_destino
            )
            inv_destino.stock_actual += self.cantidad
            inv_destino.save()

            t_entrada = TipoMovimiento.objects.filter(es_entrada=True, codigo__icontains="TRANSFERENCIA").first()
            if not t_entrada: t_entrada = TipoMovimiento.objects.filter(es_entrada=True).first()

            MovimientoInventario.objects.create(
                inventario=inv_destino,
                stock_lote=nuevo_lote,
                tipo_movimiento=t_entrada,
                usuario=usuario,
                detalle_transferencia=self,
                bodega_origen=self.detalle.transferencia.bodega_origen,
                bodega_destino=bodega_destino,
                cantidad=self.cantidad,
                stock_antes=inv_destino.stock_actual - self.cantidad,
                stock_despues=inv_destino.stock_actual,
                valor_unitario=nuevo_lote.costo_compra_lote,
                valor_total=nuevo_lote.costo_compra_lote * self.cantidad,
                motivo=f"Recepción TRF {self.detalle.transferencia.codigo}"
            )

           
            self.stock_lote_destino = nuevo_lote
            self.save() 

           
            total_real = self.detalle.lotes_asignados.filter(
                stock_lote_destino__isnull=False
            ).aggregate(t=models.Sum('cantidad'))['t'] or 0
            
            cantidad_final = min(total_real, self.detalle.cantidad_solicitada)
            
            self.detalle.cantidad_atendida = cantidad_final
            self.detalle.save()
            
            self.detalle.transferencia.actualizar_estado_recepcion()

        return nuevo_lote


class Compra(models.Model):
    
    fecha = models.DateTimeField(auto_now_add=True)
    numero_factura = models.CharField(max_length=50)
    observacion = models.TextField(blank=True, null=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    
    proveedor = models.ForeignKey('Proveedor', on_delete=models.CASCADE)
    bodega_destino = models.ForeignKey('Bodega', on_delete=models.CASCADE)
    usuario = models.ForeignKey('auth.User', on_delete=models.PROTECT) 
    
    def __str__(self):
        return f"CMP-{self.id} | {self.proveedor.nombre}"

class DetalleCompra(models.Model):
    compra = models.ForeignKey(Compra, related_name='detalles', on_delete=models.CASCADE)
    producto = models.ForeignKey('Producto', on_delete=models.PROTECT)
    
    cantidad = models.PositiveIntegerField()
    costo_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    total_linea = models.DecimalField(max_digits=12, decimal_places=2)
   
    lote_generado = models.ForeignKey('StockLote', on_delete=models.SET_NULL, null=True, blank=True)

    def save(self, *args, **kwargs):
        self.total_linea = self.cantidad * self.costo_unitario
        super().save(*args, **kwargs)