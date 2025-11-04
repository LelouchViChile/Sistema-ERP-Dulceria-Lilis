from django import forms
from .models import Producto

class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = "__all__"
        error_messages = {
            "sku": {"unique": "Ya existe un producto con ese SKU.", "invalid": "Formato de SKU inválido."},
            "ean_upc": {"unique": "Este EAN/UPC ya está registrado.", "invalid": "EAN/UPC debe tener 8/12/13/14 dígitos."},
        }

    def clean(self):
        data = super().clean()
        costo = data.get("costo_estandar")
        precio = data.get("precio_venta")
        if costo is not None and precio is not None and precio < costo:
            raise forms.ValidationError("El precio de venta no puede ser menor que el costo estándar.")
        return data
