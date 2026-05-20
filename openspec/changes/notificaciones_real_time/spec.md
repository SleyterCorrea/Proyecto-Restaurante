# Spec: Notificaciones de Platos Listos

## Escenarios

### Escenario: Notificar al mozo cuando un plato está listo
- **Given** que el mozo "Carlos" tiene la sesión abierta en el salón
- **And** el cocinero tiene el pedido de la Mesa 5 en la pantalla KDS
- **When** el cocinero marca el plato "Ceviche" como **LISTO**
- **Then** el sistema MUST enviar un mensaje por WebSocket al grupo de mozos
- **And** el mozo "Carlos" MUST recibir una notificación visual que diga: "Mesa 5: Ceviche está listo para entregar"

### Escenario: Notificación incluye nombre del cliente
- **Given** que la Mesa 8 está a nombre de "Sleyter Correa"
- **When** el plato "Lomo Saltado" de esa mesa se marca como **LISTO**
- **Then** la notificación MUST incluir el nombre del cliente: "Mesa 8 (Sleyter Correa): Lomo Saltado listo"

## Reglas de Negocio
- Las notificaciones solo se envían para el estado **LISTO**.
- Todos los usuarios con rol `MOZO` o `ADMIN` deben recibir las alertas.
- Las notificaciones deben ser no intrusivas (Toasts auto-desaparecibles).
