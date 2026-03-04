from django import forms
from django.core.exceptions import ValidationError
from ..models import (
    Impuesto,
    TipoAlmacenamiento,
    TipoIdentificacion,
    ClaseProducto,
    PerfilCaducidad,
    EstadoLote,
    Pais,
    TipoMovimiento,
    EstadoPedido,
)

class ImpuestoForm(forms.ModelForm):
    class Meta:
        model = Impuesto
        fields = ['nombre', 'porcentaje', 'es_activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: IVA 15%'}),
            'porcentaje': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'}),
            'es_activo': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }

class TipoAlmacenamientoForm(forms.ModelForm):
    class Meta:
        model = TipoAlmacenamiento
        fields = ['codigo', 'descripcion', 'es_activo']
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control text-uppercase', 'placeholder': 'Ej: AMBIENTE'}),
            'descripcion': forms.TextInput(attrs={'class': 'form-control'}),
            'es_activo': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }

    def clean_es_activo(self):
        es_activo = self.cleaned_data.get('es_activo')
        if self.instance.pk and not es_activo:
            if self.instance.zonas.exists() or self.instance.productos.exists():
                raise ValidationError("No se puede desactivar: Este tipo está asignado a zonas o productos existentes.")
        return es_activo

class TipoIdentificacionForm(forms.ModelForm):
    class Meta:
        model = TipoIdentificacion
        fields = ['codigo', 'descripcion', 'es_activo']
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control text-uppercase', 'placeholder': 'Ej: RUC'}),
            'descripcion': forms.TextInput(attrs={'class': 'form-control'}),
            'es_activo': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }

    def clean_es_activo(self):
        es_activo = self.cleaned_data.get('es_activo')
        if self.instance.pk and not es_activo:
            if self.instance.proveedores.exists() or self.instance.clientes.exists():
                raise ValidationError("No se puede desactivar: El tipo de identificación está en uso por terceros.")
        return es_activo

class ClaseProductoForm(forms.ModelForm):
    class Meta:
        model = ClaseProducto
        fields = ['codigo', 'descripcion', 'es_activo']
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control text-uppercase', 'placeholder': 'Ej: UNIDAD'}),
            'descripcion': forms.TextInput(attrs={'class': 'form-control'}),
            'es_activo': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }

    def clean_es_activo(self):
        es_activo = self.cleaned_data.get('es_activo')
        if self.instance.pk and not es_activo:
            if self.instance.productos.exists():
                raise ValidationError("No se puede desactivar: Esta clase tiene productos vinculados.")
        return es_activo

class PerfilCaducidadForm(forms.ModelForm):
    class Meta:
        model = PerfilCaducidad
        fields = ['codigo', 'descripcion', 'requiere_caducidad', 'dias_bloqueo_previo', 'estrategia_requerida', 'es_activo']
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control text-uppercase', 'placeholder': 'Ej: PERFIL_FIFO'}),
            'descripcion': forms.TextInput(attrs={'class': 'form-control'}),
            'requiere_caducidad': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
            'dias_bloqueo_previo': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'estrategia_requerida': forms.Select(attrs={'class': 'form-select'}),
            'es_activo': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        estrategia = cleaned_data.get("estrategia_requerida")
        requiere_cad = cleaned_data.get("requiere_caducidad")
        dias_bloqueo = cleaned_data.get("dias_bloqueo_previo")

        if estrategia == 'FIFO':
            if requiere_cad:
                self.add_error('requiere_caducidad', "Inconsistencia: La estrategia FIFO no utiliza control de caducidad.")
            if dias_bloqueo and dias_bloqueo > 0:
                self.add_error('dias_bloqueo_previo', "Inconsistencia: FIFO no permite días de bloqueo.")

        if estrategia == 'FEFO' and not requiere_cad:
            self.add_error('requiere_caducidad', "Obligatorio: La estrategia FEFO requiere activar el control de caducidad.")

        return cleaned_data

class EstadoLoteForm(forms.ModelForm):
    class Meta:
        model = EstadoLote
        fields = ['codigo', 'descripcion', 'es_vendible', 'marca_disponible', 'marca_agotado', 'marca_bloqueado', 'marca_vencido', 'es_activo']
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: DISPONIBLE'}),
            'descripcion': forms.TextInput(attrs={'class': 'form-control'}),
            'es_activo': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }

class EstadoPedidoForm(forms.ModelForm):
    class Meta:
        model = EstadoPedido
        fields = ['codigo', 'descripcion', 'es_activo'] 
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control text-uppercase'}),
            'descripcion': forms.TextInput(attrs={'class': 'form-control'}),
            'es_activo': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }

    def clean_es_activo(self):
        es_activo = self.cleaned_data.get('es_activo')
        if self.instance.pk and not es_activo:
            if self.instance.pedidos.exists():
                raise ValidationError("No se puede desactivar: Hay pedidos registrados con este estado.")
        return es_activo

class TipoMovimientoForm(forms.ModelForm):
    class Meta:
        model = TipoMovimiento
        fields = ['codigo', 'descripcion', 'afecta_stock', 'es_entrada', 'es_salida', 'requiere_pedido', 'requiere_motivo_detallado', 'es_activo']
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control text-uppercase'}),
            'descripcion': forms.TextInput(attrs={'class': 'form-control'}),
            'es_activo': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }

class PaisForm(forms.ModelForm):
    class Meta:
        model = Pais
        fields = ['codigo_iso', 'nombre', 'es_activo']
        widgets = {
            'codigo_iso': forms.TextInput(attrs={'class': 'form-control text-uppercase', 'placeholder': 'Ej: EC'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Ecuador'}),
            'es_activo': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }

    def clean_es_activo(self):
        es_activo = self.cleaned_data.get('es_activo')
        if self.instance.pk and not es_activo:
            # CORRECCIÓN DE ERROR: Usar los relacionados directos reconocidos por Django
            if self.instance.proveedores.exists() or self.instance.clientes.exists():
                raise ValidationError("No se puede desactivar: El país está asignado a clientes o proveedores.")
        return es_activo