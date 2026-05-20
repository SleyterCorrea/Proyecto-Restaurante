# Archive Report: Gestión de Identidad del Cliente

## Resumen
Se implementó la capacidad de capturar y visualizar el nombre del cliente en todo el ciclo de vida del pedido, mejorando la trazabilidad y la atención al cliente.

## Cambios Realizados
- **Modelo**: Adición de `nombre_cliente` a `Comanda`.
- **UI Mesero**: Modal de selección de mesa y sidebar de pedidos muestran el nombre.
- **KDS**: Los tickets de cocina ahora incluyen la identidad del cliente.
- **Caja**: La interfaz de cobro y el PDF de la boleta muestran el nombre.
- **Plano de Mesas**: Las tarjetas de mesa y el modal de detalle integran el nombre.

## Verificación
- Pruebas manuales realizadas en KDS y Caja.
- Verificación de la migración de base de datos.
- Validación de accesibilidad en el renderizado de nombres.

## Estado Final
Implementado y documentado en `openspec/specs/comandas_mesas.md`.
