# Especificación Técnica: Gestión de Menú y Auditoría

## 1. Módulo de Gestión de Menú

### 1.1. Arquitectura
Se ha implementado un sistema CRUD completo utilizando **Django REST Framework (DRF)** en el backend y **Alpine.js** en el frontend para una experiencia de usuario fluida y reactiva sin recargas de página.

### 1.2. Componentes Clave
- **Frontend**: `templates/admin_panel/menu.html` utiliza un componente Alpine.js centralizado que maneja el estado de categorías y platos.
- **Backend**: `apps/menu/views.py` expone `CategoriaViewSet` y `PlatoViewSet` con permisos restringidos a `EsAdmin`.
- **Media**: Los platos ahora soportan el campo `imagen`. El frontend envía los datos mediante `FormData` para soportar la subida de archivos binarios (`multipart/form-data`).

### 1.3. Endpoints
- `GET /api/menu/categorias/`: Listado ordenado de categorías.
- `GET /api/menu/platos/`: Listado de platos (filtrable por categoría en frontend).
- `POST /api/menu/platos/`: Creación de plato con imagen.

---

## 2. Sistema de Auditoría

### 2.1. Modelo de Datos (`AuditLog`)
Ubicado en `apps.usuarios.models`, el modelo captura:
- **Usuario**: Quién realizó la acción.
- **Acción**: CREACION, EDICION, ELIMINACION, LOGIN.
- **Entidad**: Nombre de la tabla/dominio afectado (PLATOS, CATEGORIA, USUARIO, etc.).
- **Detalle Anterior/Nuevo**: Captura del estado del objeto en formato JSON antes y después del cambio.
- **Contexto**: Dirección IP y User Agent del navegador.

### 2.2. Utilidad de Logging
Se creó `apps/usuarios/utils.py` con la función `log_auditoria` para centralizar la creación de registros, abstrayendo la lógica de captura de IP y metadatos del request.

### 2.3. Integración
- **ViewSets**: Se sobrescribieron los métodos `perform_create`, `perform_update` y `perform_destroy` en los controladores de Menú y Usuarios para disparar el log automáticamente.
- **Login**: Se sobrescribió el método `post` de `LoginView` para registrar accesos exitosos.

### 2.4. Interfaz de Usuario
`templates/admin_panel/auditoria.html` permite:
- Visualización cronológica de logs.
- Filtros por acción y entidad.
- Modal de detalle con comparación visual de los cambios en crudo (JSON).

---

## 3. Guía de Estilo UI (Actualización)
Se han estandarizado los siguientes patrones visuales:
- **Acción Primaria**: Botones con fondo `bg-primary` (Azul/Indigo) y texto oscuro para máximo contraste.
- **Hovers de Navegación**: Uso de `hover:text-primary` en lugar de blanco para asegurar legibilidad en fondos claros (Modo Claro).
- **Consistencia**: Todos los módulos administrativos (Menú, Inventario, Personal, Auditoría) comparten la misma estructura de "Glass Card" y cabeceras dinámicas.
