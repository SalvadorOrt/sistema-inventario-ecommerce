
from django import forms
from ..models import Bodega, ZonaAlmacenamiento, Rack, UbicacionFisica

class BodegaForm(forms.ModelForm):
    class Meta:
        model = Bodega
        fields = ['nombre', 'direccion', 'referencia', 'es_activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Bodega Central...'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Dirección física...'}),
            'referencia': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Puntos de referencia...'}),
            'es_activo': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }


class ZonaAlmacenamientoForm(forms.ModelForm):
    class Meta:
        model = ZonaAlmacenamiento
        fields = ['bodega', 'nombre', 'tipo_almacenamiento', 'es_activo']
        widgets = {
            'bodega': forms.Select(attrs={'class': 'form-select select2-enable'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Recepción, Cuarentena...'}),
            'tipo_almacenamiento': forms.Select(attrs={'class': 'form-select'}),
            'es_activo': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        
        if self.instance and self.instance.pk:
            self.fields['bodega'].disabled = True
        
       
        elif 'bodega' in self.initial and self.initial['bodega']:
            self.fields['bodega'].disabled = True
            self.fields['bodega'].widget.attrs['readonly'] = True

class RackForm(forms.ModelForm):
    # Campo auxiliar: No se guarda en la tabla Rack directamente, sirve para el bucle en la vista.
    # SE HAN ELIMINADO min_value y max_value para quitar los límites.
    cantidad_niveles = forms.IntegerField(
        initial=1,
        label="Altura (Niveles)",
        widget=forms.NumberInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Ej: 50', 
            'style': 'font-weight: bold;'
        }),
        help_text="El sistema generará automáticamente las ubicaciones para esta altura."
    )

    class Meta:
        model = Rack
        # No incluimos 'codigo' porque se genera automáticamente (A, B, C...)
        fields = ['zona', 'descripcion', 'es_activo'] 
        widgets = {
            'zona': forms.Select(attrs={'class': 'form-select select2-enable'}),
            'descripcion': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Opcional: Ej. Pasillo A...'
            }),
            'es_activo': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if self.instance and self.instance.pk:
           
            if 'cantidad_niveles' in self.fields:
                self.fields['cantidad_niveles'].widget = forms.HiddenInput()
                self.fields['cantidad_niveles'].required = False
            
            self.fields['zona'].disabled = True
            
        elif 'zona' in self.initial and self.initial['zona']:
            self.fields['zona'].disabled = True
            self.fields['zona'].widget.attrs['readonly'] = True
            self.fields['cantidad_niveles'].required = True