from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import Usuario, Rol

class RolSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rol
        fields = ['id', 'nombre', 'descripcion']

class UsuarioSerializer(serializers.ModelSerializer):
    rol_nombre = serializers.ReadOnlyField(source='rol.nombre')

    class Meta:
        model = Usuario
        fields = [
            'id', 'username', 'nombres', 'apellidos', 'email', 'rol', 'rol_nombre', 
            'activo', 'dni', 'tipo_trabajo', 'turno', 'fecha_ingreso', 'fecha_termino', 'password'
        ]
        extra_kwargs = {
            'password': {'write_only': True, 'required': False},
            'username': {'required': True}
        }

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = Usuario(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Añadir claims personalizados al payload del JWT
        token['username'] = user.username
        token['rol'] = user.rol.nombre
        token['nombres'] = user.nombres
        token['apellidos'] = user.apellidos
        
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        
        # Añadir datos del usuario a la respuesta del login
        data['usuario'] = {
            'id': self.user.id,
            'username': self.user.username,
            'nombres': self.user.nombres,
            'apellidos': self.user.apellidos,
            'rol': self.user.rol.nombre,
            'email': self.user.email
        }
        return data
