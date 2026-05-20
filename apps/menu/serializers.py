from rest_framework import serializers
from .models import Categoria, Plato

class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = '__all__'

class PlatoSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.ReadOnlyField(source='categoria.nombre')
    imagen_url = serializers.ReadOnlyField()

    class Meta:
        model = Plato
        fields = '__all__'
