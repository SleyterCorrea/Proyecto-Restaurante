# Tasks: Funcionalidad de unir mesas (máximo 3)

## Phase 1: Foundation & Data Model
- [x] 1.1 Modificar `apps/comandas/models.py`: agregar `mesas_adicionales` (M2M) y property `get_todas_las_mesas`.
- [x] 1.2 Ejecutar migraciones de Django para impactar cambios en DB.

## Phase 2: Core API & Backend Logic
- [x] 2.1 Refactorizar `api_crear_comanda` en `apps/comandas/views.py` para procesar lista de `mesa_ids`.
- [x] 2.2 Implementar validación de límite (3 mesas) y estado `LIBRE` en `api_crear_comanda`.
- [x] 2.3 Asegurar atomicidad en la ocupación de mesas satélites dentro de la transacción.
- [x] 2.4 Actualizar `api_liberar_mesa` en `apps/comandas/views.py` para liberar todo el grupo asociado. (Nota: Se actualizó `procesar_cobro` que es donde ocurre la liberación real).
- [x] 2.5 Ajustar `api_estado_actual` en `apps/mesas/views.py` para que el polling reconozca uniones.

## Phase 3: Frontend Wiring (Alpine.js)
- [x] 3.1 Modificar `templates/mesero/toma_pedidos.html`: cambiar selección simple a array `mesasSeleccionadas`.
- [x] 3.2 Actualizar el modal de selección de mesa para permitir multi-click y validar el límite de 3 en caliente.
- [x] 3.3 Actualizar `enviarPedido` para enviar el nuevo payload `mesa_ids` al backend.

## Phase 4: Testing & Verification
- [x] 4.1 Crear test de integración que valide la creación de comanda con 3 mesas y su liberación posterior.
- [x] 4.2 Verificar visualmente en el plano de mesas que la unión se refleje correctamente.
