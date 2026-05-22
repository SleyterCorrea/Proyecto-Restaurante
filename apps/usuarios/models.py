from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

class Rol(models.Model):
    """Modelo para los roles del sistema (MOZO, COCINERO, CAJERO, ADMIN)."""
    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.CharField(max_length=150, blank=True, null=True)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'rol'
        verbose_name = 'Rol'
        verbose_name_plural = 'Roles'

    def __str__(self):
        return self.nombre

class UsuarioManager(BaseUserManager):
    def create_user(self, username, email, password=None, **extra_fields):
        if not email:
            raise ValueError('El email es obligatorio')
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        
        # Asignar rol ADMIN por defecto si existe, o crear uno
        admin_rol, _ = Rol.objects.get_or_create(nombre='ADMIN')
        extra_fields.setdefault('rol', admin_rol)
        
        return self.create_user(username, email, password, **extra_fields)

class Usuario(AbstractBaseUser, PermissionsMixin):
    """Modelo de usuario personalizado según el esquema SQL."""
    rol = models.ForeignKey(Rol, on_delete=models.PROTECT, related_name='usuarios')
    username = models.CharField(max_length=50, unique=True)
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    email = models.EmailField(max_length=120, unique=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    dni = models.CharField(max_length=15, unique=True, null=True, blank=True)
    
    TIPO_TRABAJO_CHOICES = [
        ('FULL_TIME', 'Full Time'),
        ('PART_TIME', 'Part Time'),
    ]
    tipo_trabajo = models.CharField(max_length=20, choices=TIPO_TRABAJO_CHOICES, default='FULL_TIME')
    
    TURNO_CHOICES = [
        ('MANANA', 'Turno Mañana'),
        ('TARDE', 'Turno Tarde'),
        ('NOCHE', 'Turno Noche'),
    ]
    turno = models.CharField(max_length=20, choices=TURNO_CHOICES, default='MANANA')
    
    fecha_ingreso = models.DateField(null=True, blank=True)
    fecha_termino = models.DateField(null=True, blank=True)
    
    activo = models.BooleanField(default=True)
    
    # Campos requeridos para Django Admin/Auth
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UsuarioManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email', 'nombres', 'apellidos']

    class Meta:
        db_table = 'usuario'
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return f'{self.username} ({self.rol.nombre})'

class AuditLog(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name='logs')
    accion = models.CharField(max_length=50)
    entidad = models.CharField(max_length=50)
    entidad_id = models.BigIntegerField()
    detalle_anterior = models.JSONField(null=True, blank=True)
    detalle_nuevo = models.JSONField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True, null=True)
    fecha_evento = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'audit_log'
        verbose_name = 'Log de Auditoría'

class ConfiguracionSistema(models.Model):
    """Modelo Singleton para almacenar configuraciones globales del sistema (ej. Modo Claro/Oscuro)."""
    tema_oscuro = models.BooleanField(default=True, help_text="Define si todo el sistema debe estar en modo oscuro.")

    class Meta:
        db_table = 'configuracion_sistema'
        verbose_name = 'Configuración del Sistema'
        verbose_name_plural = 'Configuraciones del Sistema'

    @classmethod
    def get_instancia(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj

    def __str__(self):
        return f"Configuración Global (Oscuro: {self.tema_oscuro})"
