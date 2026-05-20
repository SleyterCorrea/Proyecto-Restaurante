# 🍽️ SYSTEM_RESTAURANT: Documentación Maestra de Contexto

## 1. Visión General
**Nombre del Proyecto**: RestaurantOS
**Propósito Principal**: Un sistema integral de gestión para restaurantes (Point of Sale + Kitchen Display System). Permite a los meseros tomar pedidos de forma ágil desde cualquier dispositivo móvil (unificando mesas si es necesario), envía las comandas en tiempo real a la cocina (KDS) y centraliza la caja, inventario y reportes para la administración. Todo bajo una interfaz unificada, rápida y con estética "Dark Premium Glassmorphism".

---

## 2. Stack Tecnológico

| Capa | Tecnología | Descripción |
|------|------------|-------------|
| **Backend** | Python 3.11 + Daphne (ASGI) | Servidor de aplicaciones asíncrono para soportar WebSockets y HTTP. |
| **API** | Django REST Framework | Exposición de endpoints JSON para consumo del frontend. |
| **Frontend** | HTML5 + Tailwind CSS | Maquetado moderno, utility-first para lograr efectos glassmorphism. |
| **Interactividad** | Alpine.js v3 + WebSockets | Manejo de estado reactivo y notificaciones en tiempo real (Push). |
| **Mensajería** | Redis | Canal de comunicación (Channel Layer) para eventos en tiempo real. |
| **Base de Datos** | PostgreSQL | Motor de base de datos oficial corriendo en Docker. |
| **Testing** | Pytest + Django Test | Pruebas unitarias para validar la lógica de negocio (ej. unión de mesas). |
| **Diseño** | CSS Variables + Tailwind | Sistema de temas reactivo (Claro/Oscuro) basado en tokens de diseño. |

---

## 3. Estructura de Archivos

La arquitectura se basa en aplicaciones modulares (*apps*) separadas por dominio de negocio:

```text
/Proyecto-Restaurante
├── apps/                   # Dominios de negocio (Arquitectura Modular)
│   ├── caja/               # Gestión de turnos, arqueos y métodos de pago
│   ├── comandas/           # Core: Pedidos, líneas de comanda, KDS (Cocina)
│   ├── inventario/         # Control de stock, insumos, unidades y recetas
│   ├── menu/               # Catálogo de platos, precios y categorías
│   ├── mesas/              # Control del salón, pisos y estados (Libre/Ocupada)
│   ├── reportes/           # Dashboard administrativo y KPIs
│   └── usuarios/           # Autenticación, roles (Admin, Mozo, Cocinero) y logs
├── restaurant/             # Configuración central (settings.py, urls.py base)
├── templates/              # Vistas HTML renderizadas por Django
│   ├── base.html           # Layout principal (Dark theme, Navbar)
│   ├── mesero/             # Vistas de toma de pedidos y plano de mesas
│   └── cocina/             # Vista del KDS (Kitchen Display System)
├── static/                 # Archivos estáticos (imágenes, CSS base, JS global)
├── openspec/               # (SDD) Documentación técnica de features en desarrollo
├── tests/                  # Suite de pruebas unitarias y de integración
└── manage.py               # Entrypoint de ejecución
```

---

## 4. Esquema de Base de Datos

A continuación, la relación de las tablas clave del sistema y sus llaves primarias/foráneas (PK/FK).

### Usuarios y Seguridad
- **`Usuario`**: Custom User (PK). Tiene `FK(Rol)`. 
  - Propiedades: `username`, `email`, `dni`, `tipo_trabajo` (Full/Part Time), `fecha_ingreso`, `fecha_termino`.
- **`Rol`**: Define permisos (Admin, Mozo, Cocinero, Cajero).
- **`AuditLog`**: Registro de trazabilidad. Captura `usuario`, `accion` (CREACION, EDICION, ELIMINACION, LOGIN), `entidad`, `detalles` (JSON anterior/nuevo) e `IP`.

### Salón y Menú
- **`Zona`**: Área del local (Ej. Terraza, Salón principal).
- **`Mesa`**: `FK(Zona)`. Propiedades: `numero`, `capacidad`, `estado` (Libre, Ocupada, Reservada, Limpieza, Por Pagar).
- **`Categoria`**: Clasificación del menú (Bebidas, Entradas). Soporta íconos dinámicos.
- **`Plato`**: `FK(Categoria)`. Propiedades: `nombre`, `precio`, `tiempo_preparacion`, `imagen` (Soporte para fotos reales).

### Core transaccional (Comandas)
- **`Comanda`**: Cabecera del pedido.
  - `FK(Mesa)` (Mesa principal).
  - `M2M(Mesa)` (Mesas adicionales unidas al mismo pedido).
  - `FK(Usuario)` (Mozo que atiende).
  - `nombre_cliente`: Identificación del cliente/grupo.
  - Estado: `ABIERTA`, `EN_PREPARACION`, `LISTA` (para cobrar), `COBRADA`, `ANULADO`.
- **`LineaComanda`**: Detalle del pedido.
  - `FK(Comanda)`, `FK(Plato)`.
  - Estado: `PENDIENTE`, `EN_PREP`, `LISTO`, `ANULADO`.

### Inventario y Caja
- **`Insumo`**: Ingrediente físico (Ej. Tomate). `FK(UnidadMedida)`.
- **`RecetaInsumo`**: Relaciona `FK(Plato)` con `FK(Insumo)`. Resta stock automáticamente.
- **`CajaTurno`**: Jornada de caja. `FK(Usuario)`.
- **`Pago`**: Transacción monetaria. `FK(Comanda)`, `FK(MetodoPago)`.

---

## 5. Lógica de Negocio y Endpoints

El sistema opera mediante una combinación de vistas HTML clásicas y endpoints REST asíncronos consumidos por Alpine.js.

### APIs Núcleo (JSON)
* **`GET /api/mesas/estado-actual/`**: (Polling). Retorna el estado en tiempo real del salón. Incluye las comandas activas embebidas para re-renderizar el plano dinámicamente.
* **`POST /api/comandas/crear/`**: Crea una orden de forma atómica. Soporta **unión de múltiples mesas** (`mesa_ids: [1, 2, 3]`), verifica stock de insumos por receta y bloquea las mesas a `OCUPADA`.
* **`POST /api/comandas/<id>/platos/`**: Añade nuevos platos a una comanda existente (incluso si los anteriores ya están en preparación).
* **`GET /api/cocina/pendientes/`**: Lista filtrada para el KDS de la cocina (solo ítems `PENDIENTE` y `EN_PREP`).
* **`PATCH /api/lineas/<id>/estado/`**: Avanza el flujo de preparación (`PENDIENTE` -> `EN_PREP` -> `LISTO`). Dispara automáticamente una **notificación vía WebSocket** al mozo.
* **`WS /ws/notificaciones/`**: Canal bidireccional para alertas en tiempo real (Notificaciones de platos listos).
* **`POST /api/comandas/mesa/<id>/liberar/`**: Cierra la comanda en el sistema de mesas y la manda a caja. Cambia el estado de la mesa a `POR_PAGAR` (celeste).
* **`POST /api/caja/comanda/<id>/pagar/`**: Procesa el pago, genera la boleta PDF y libera definitivamente la mesa (`LIBRE`).
* **`GET /api/caja/historial/`**: Consulta histórica de pagos filtrados por fechas. Restringido al día actual para CAJEROS.
* **`GET/POST/PATCH /api/trabajadores/`**: CRUD completo de personal (Solo Admin). Permite gestionar altas, bajas, roles y contraseñas.
* **`GET/POST/PUT/DELETE /api/menu/platos/`**: Gestión administrativa de platos incluyendo carga de imágenes (`multipart/form-data`).
* **`GET/POST/PUT/DELETE /api/menu/categorias/`**: Gestión administrativa de categorías e íconos.
* **`GET /api/auditoria-logs/`**: Consulta de logs de actividad del sistema con filtros avanzados por usuario, acción y entidad.

---

## 6. Estado del Desarrollo

🟢 **Funcional al 100% (Implementado y Probado)**
- **Seguridad**: Autenticación y Autorización basada en Roles.
- **Flujo del Mesero**: Plano interactivo, selector de mesas, toma de pedidos dinámica con catálogo.
- **Flujo de Cocina (KDS)**: Gestión de tickets en tiempo real, bloqueo de edición en platos en proceso.
- **Gestión Multi-Mesa**: Unión de hasta 3 mesas bajo una cuenta unificada.
- **Módulo de Caja/Pagos**: Cobro de comandas, múltiples métodos de pago, cálculo de vuelto y generación de boletas PDF con QR.
- **Historial de Ventas Interactivo**: Visualización de pagos integrados en el panel de cobro, con filtros por fecha y acceso a boletas.
- **Estado de Mesas Intermedio**: Implementación del estado "Por Pagar" (celeste) que separa la solicitud de cuenta del cobro final.
- **Identificación de Clientes**: Gestión de nombres de clientes persistente en todo el ciclo del pedido.
- **Sistema de Temas**: Modo Claro y Oscuro dinámico con persistencia en base de datos.
- **Agregado Continuo**: Posibilidad de añadir platos extra a mesas ya ocupadas, con opción de eliminar platos individuales del pedido actual.
- **Notificaciones en Tiempo Real**: Alertas instantáneas a mozos (Push) mediante WebSockets cuando la cocina termina un plato (Cross-role validation).
- **Entorno de Contenedores**: Infraestructura de desarrollo estandarizada con Docker, Redis y PostgreSQL.
- **Gestión de Personal**: Panel administrativo para registrar trabajadores con DNI, tipo de contrato y roles específicos.
- **Seguridad en Login**: Implementación de visibilidad de contraseña (eye-toggle) y estética glassmorphism optimizada.
- **UX de Pedidos**: Validación de límite de mesas (3) integrada en el modal con auto-ocultado tras 10 segundos.
- **Documentación por Rol**: Acceso directo a manuales de uso personalizados según el rol del usuario logueado.
- **Módulo de Gestión de Menú**: CRUD dinámico de categorías y platos con carga de imágenes y previsualización en tiempo real.
- **Sistema de Auditoría**: Trazabilidad completa de acciones críticas, cambios en el menú, gestión de usuarios e inicios de sesión.
- **UX Optimizada**: Hovers dinámicos y botones con código de colores (Azul Primario para acciones principales) para máxima claridad en modo claro/oscuro.

🟡 **A Medio Hacer / Pendiente (WIP)**
- **Reportes/Dashboard Administrativo**: Finalizar la carga de gráficos de métricas (ingresos, platos más vendidos) en tiempo real.
- **Descuento de Inventario Automático**: Conectar totalmente el trigger que reste insumos al confirmar una línea como `LISTO`.

---

## 7. Guía de Estilo y Convenciones

1. **Arquitectura "Fat Models, Thin Views"**: 
   La lógica de negocio reside predominantemente en los modelos (Ej. `comanda.calcular_totales()`, `comanda.marcar_como_lista()`) para mantener los controladores limpios y testeables.
2. **Atomicidad**: 
   Toda creación o modificación que involucre más de un registro (Ej. Crear Comanda + Líneas + Cambiar estado de Mesa) se envuelve estrictamente en `transaction.atomic()`.
3. **Idiomas y Nomenclatura**:
   - Negocio y Modelos: Español (`Comanda`, `Plato`, `Mesa`) para reflejar exactamente el lenguaje de los usuarios.
   - Framework/Código genérico: Estándares de Python en Inglés o convenciones de Django (`created_at`, `updated_at`, `ForeignKey`).
4. **Alpine.js para Reactividad**:
   Se evita el uso excesivo de Vanilla JS o SPAs pesadas (React/Vue). Se delega el estado UI a Alpine.js (`x-data`, `x-show`, `x-for`) directamente en las plantillas Django para desarrollo ultra-rápido.
5. **Estética Visual e Inclusión (UI)**:
   - **Diseño Adaptativo**: Paleta de colores basada en CSS Variables definidas en `base.html`.
   - **Sistema de Temas**: Soporte nativo para Modo Claro y Oscuro (Admin-controlled), cumpliendo con las guías WCAG de accesibilidad.
   - **Glassmorphism**: Componentes semitransparentes con desenfoque dinámico según el tema.
   - **Feedback Visual**: Estados de carga y transiciones suaves para una experiencia premium.
