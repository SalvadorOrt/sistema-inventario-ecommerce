from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from ..models import Producto, ImagenProducto, Categoria, Marca, Proveedor, Cliente

class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ['nombre', 'prefijo_sku', 'descripcion', 'es_activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'prefijo_sku': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'es_activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class MarcaForm(forms.ModelForm):
    class Meta:
        model = Marca
        fields = ['nombre', 'descripcion', 'es_activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'es_activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = ['nombre', 'tipo_identificacion', 'numero_identificacion', 'pais', 'correo', 'telefono', 'es_activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_identificacion': forms.Select(attrs={'class': 'form-select js-select2'}),
            'numero_identificacion': forms.TextInput(attrs={'class': 'form-control'}),
            'pais': forms.Select(attrs={'class': 'form-select js-select2'}),
            'correo': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'es_activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['tipo_cliente', 'nombres', 'apellidos', 'codigo', 'tipo_identificacion', 'numero_identificacion', 'correo', 'telefono', 'es_activo']
        widgets = {
            'tipo_cliente': forms.Select(attrs={'class': 'form-select js-select2'}),
            'nombres': forms.TextInput(attrs={'class': 'form-control'}),
            'apellidos': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_identificacion': forms.Select(attrs={'class': 'form-select js-select2'}),
            'numero_identificacion': forms.TextInput(attrs={'class': 'form-control'}),
            'correo': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'es_activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = [
            "codigo_sku", "codigo_barras", "nombre", "descripcion",
            "precio_venta", "costo_compra", 
            "marca", "categoria", "clase_producto", 
            "tipo_almacenamiento", "perfil_caducidad", "impuesto",
            "estrategia_salida", "notas_manejo", "es_activo"
        ]
        widgets = {
            "nombre": forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del producto'}),
            "codigo_barras": forms.TextInput(attrs={'class': 'form-control'}),
            "descripcion": forms.Textarea(attrs={'class': 'form-control', "rows": 2}),
            
            # Selects
            "marca": forms.Select(attrs={'class': 'form-select'}),
            "categoria": forms.Select(attrs={'class': 'form-select'}),
            "clase_producto": forms.Select(attrs={'class': 'form-select'}),
            "tipo_almacenamiento": forms.Select(attrs={'class': 'form-select'}),
            "perfil_caducidad": forms.Select(attrs={'class': 'form-select'}),
            "impuesto": forms.Select(attrs={'class': 'form-select'}),
            "estrategia_salida": forms.Select(attrs={'class': 'form-select'}),
            
            "notas_manejo": forms.Textarea(attrs={'class': 'form-control', "rows": 2}),
            "precio_venta": forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            "costo_compra": forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            "es_activo": forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Configuración del SKU (Solo lectura visual)
        if 'codigo_sku' in self.fields:
            self.fields['codigo_sku'].widget.attrs.update({
                'readonly': 'readonly',
                'class': 'form-control bg-light text-muted fw-bold',
                'placeholder': '[ AUTO-GENERADO AL GUARDAR ]'
            })
            self.fields['codigo_sku'].required = False

    def clean_codigo_sku(self):
        return self.cleaned_data.get("codigo_sku")

    def clean_precio_venta(self):
        precio = self.cleaned_data.get("precio_venta")
        if precio is not None and precio < 0:
            raise ValidationError("El precio de venta no puede ser negativo.")
        return precio


class ImagenProductoForm(forms.ModelForm):
    class Meta:
        model = ImagenProducto
    
        fields = ['imagen', 'orden']
        
        widgets = {
            'imagen': forms.FileInput(attrs={
                'class': 'form-control form-control-sm js-file-input', 
                'accept': 'image/*'
            }),
            
          
            'orden': forms.HiddenInput(attrs={'class': 'js-input-orden'}), 
        }


ImagenProductoFormSet = inlineformset_factory(
    parent_model=Producto,
    model=ImagenProducto,
    form=ImagenProductoForm,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
    max_num=5,
    validate_max=True
)

class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ['nombre', 'prefijo_sku', 'descripcion', 'es_activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'prefijo_sku': forms.TextInput(attrs={
                'class': 'form-control text-uppercase', 
                'placeholder': 'Ej: ELE', 
                'maxlength': '4'
            }),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'es_activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_prefijo_sku(self):
        return self.cleaned_data['prefijo_sku'].upper()
    

class MarcaForm(forms.ModelForm):
    class Meta:
        model = Marca
        fields = ['nombre', 'descripcion', 'es_activo']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control', 
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3, 
                'placeholder': 'Breve descripción de la marca o notas internas...'
            }),
            'es_activo': forms.CheckboxInput(attrs={
                'class': 'form-check-input', 
                'role': 'switch'
            }),
        }



class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = ['nombre', 'tipo_identificacion', 'numero_identificacion', 
                  'pais', 'telefono', 'correo', 'direccion', 'es_activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Razón Social o Nombre'}),
            'tipo_identificacion': forms.Select(attrs={'class': 'form-select select2-enable'}), # Usaremos select2 aquí
            'numero_identificacion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'RUC / Cédula / Tax ID'}),
            'pais': forms.Select(attrs={'class': 'form-select select2-enable'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+593...'}),
            'correo': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'contacto@empresa.com'}),
            'direccion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'es_activo': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = [
            'tipo_cliente', 'tipo_identificacion', 'numero_identificacion',
            'nombres', 'apellidos', 'correo', 'telefono', 'direccion', 
            'pais', 'es_activo'
        ]
        widgets = {
            'tipo_cliente': forms.Select(attrs={'class': 'form-select select2-enable'}),
            'tipo_identificacion': forms.Select(attrs={'class': 'form-select select2-enable'}),
            'numero_identificacion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Identificación'}),
            'nombres': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombres'}),
            'apellidos': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apellidos'}),
            'correo': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'ejemplo@correo.com'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Teléfono'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Dirección completa'}),
            'pais': forms.Select(attrs={'class': 'form-select select2-enable'}),
            'es_activo': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }




