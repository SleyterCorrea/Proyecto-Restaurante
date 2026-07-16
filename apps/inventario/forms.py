from django import forms
from django.core.exceptions import ValidationError

from apps.core.exceptions import AppError

from .models import Insumo, RecetaInsumo, UnidadMedida
from .services import InventarioService


class InsumoAdminForm(forms.ModelForm):
    class Meta:
        model = Insumo
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        magnitud_id = self.data.get('magnitud') or getattr(
            self.instance, 'magnitud_id', None
        )
        unidades = UnidadMedida.objects.filter(activo=True).select_related('magnitud')
        self.fields['unidad_medida'].queryset = (
            unidades.filter(magnitud_id=magnitud_id)
            if magnitud_id else unidades
        )

    def clean(self):
        cleaned_data = super().clean()
        magnitud = cleaned_data.get('magnitud')
        unidad = cleaned_data.get('unidad_medida')
        if magnitud and unidad:
            try:
                InventarioService.validar_cambio_medida(
                    self.instance, magnitud, unidad
                )
            except AppError as exc:
                self.add_error('unidad_medida', str(exc))
        return cleaned_data


class RecetaInsumoAdminForm(forms.ModelForm):
    class Meta:
        model = RecetaInsumo
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        insumo_id = self.data.get('insumo') or getattr(
            self.instance, 'insumo_id', None
        )
        unidades = UnidadMedida.objects.filter(activo=True).select_related('magnitud')
        if insumo_id:
            try:
                magnitud_id = Insumo.objects.only('magnitud_id').get(
                    pk=insumo_id
                ).magnitud_id
                unidades = unidades.filter(magnitud_id=magnitud_id)
            except (Insumo.DoesNotExist, ValueError, TypeError):
                unidades = unidades.none()
        self.fields['unidad_medida'].queryset = unidades

    def clean(self):
        cleaned_data = super().clean()
        insumo = cleaned_data.get('insumo')
        unidad = cleaned_data.get('unidad_medida')
        if insumo and unidad and unidad.magnitud_id != insumo.magnitud_id:
            raise ValidationError(
                'La unidad de la receta no pertenece a la magnitud del insumo.'
            )
        return cleaned_data
