# OpenSpec: RestaurantOS

Bienvenido a la especificación técnica de RestaurantOS. Este directorio contiene la documentación viva del sistema, organizada para evitar redundancias y facilitar la incorporación de nuevos desarrolladores.

## Especificaciones de Módulo (Specs)
- [Gestión de Comandas y Mesas](file:///c:/Users/ANTHONY/Desktop/RESTAURANTE-Sleyter/Proyecto-Restaurante/openspec/specs/comandas_mesas.md): Selección multi-mesa e identificación de clientes.
- [Gestión de Personal y Trabajadores](file:///c:/Users/ANTHONY/Desktop/RESTAURANTE-Sleyter/Proyecto-Restaurante/openspec/specs/gestion_personal.md): Administración de equipo y roles.
- [Seguridad y UX de Acceso](file:///c:/Users/ANTHONY/Desktop/RESTAURANTE-Sleyter/Proyecto-Restaurante/openspec/specs/seguridad_acceso.md): Mejoras en login y visualización de contraseñas.
- [Sistema de Temas Dinámicos](file:///c:/Users/ANTHONY/Desktop/RESTAURANTE-Sleyter/Proyecto-Restaurante/openspec/specs/sistema_temas.md): Control de apariencia (Claro/Oscuro) y accesibilidad WCAG.
- [Notificaciones Real-Time](file:///c:/Users/ANTHONY/Desktop/RESTAURANTE-Sleyter/Proyecto-Restaurante/openspec/specs/notificaciones_realtime.md): WebSockets para avisos de platos listos.
- [Reportes Administrativos](file:///c:/Users/ANTHONY/Desktop/RESTAURANTE-Sleyter/Proyecto-Restaurante/openspec/specs/reportes/spec.md): Dashboard y analíticas de ventas.
- [Caja y Facturación](file:///c:/Users/ANTHONY/Desktop/RESTAURANTE-Sleyter/Proyecto-Restaurante/openspec/specs/caja_y_facturacion.md): Historial de ventas, boletas PDF y cobros.

## Historial de Cambios (Archive)
Los cambios significativos se archivan para mantener un registro histórico de las decisiones arquitectónicas:
- `caja_y_facturacion_v1`: (Hoy) Implementación del historial de ventas embebido, tickets PDF y correcciones UX/WebSockets en Mozo.
- `refinamiento_ui_gestion_personal_v1`: (Hoy) Módulo de trabajadores, validaciones de mesas y mejoras de login.
- `notificaciones_realtime_v1`: Implementación de WebSockets, Daphne y Redis.
- `unir_mesas_v1`: Implementación inicial de la unión de mesas.
- `gestion_identidad_cliente_v1`: Integración del nombre del cliente en el flujo POS/KDS.
- `dashboard-detailed-sales_v1`: Refactor del panel de analíticas.
- `complete-restaurant-system_v1`: Definición inicial del core del sistema.

## Estándares de Ingeniería
- **Clean Architecture**: Lógica de negocio en modelos, controladores delgados.
- **TDD**: Cobertura de pruebas con Pytest para procesos críticos.
- **Atomicidad**: Transacciones seguras para operaciones complejas.

---
*Nota: Para actualizaciones globales del sistema, consultar también [SYSTEM_RESTAURANT.md](file:///c:/Users/ANTHONY/Desktop/RESTAURANTE-Sleyter/Proyecto-Restaurante/SYSTEM_RESTAURANT.md).*
