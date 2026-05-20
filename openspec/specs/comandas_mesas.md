# Spec: Gestión de Comandas y Mesas

## Visión General
Este módulo permite a los mozos gestionar el flujo de pedidos, integrando la selección de múltiples mesas y la identificación de clientes.

## Requerimientos

### 1. Selección Multi-Mesa
- El sistema MUST permitir la selección de hasta tres (3) mesas por comanda.
- Al intentar seleccionar una cuarta mesa, el sistema MUST mostrar un mensaje de error ("Máximo 3 mesas permitidas.") dentro del modal de selección.
- El mensaje de error MUST desaparecer automáticamente tras diez (10) segundos y no debe interferir con la barra lateral de pedido.
- Al seleccionar varias mesas, estas deben quedar marcadas como `OCUPADA` simultáneamente.
- El sidebar de pedido MUST mostrar todas las mesas vinculadas.

### 2. Identificación del Cliente
- Al abrir una comanda, el mozo MUST ingresar el nombre del cliente.
- El nombre del cliente MUST persistir en la base de datos (`Comanda.nombre_cliente`).
- El nombre MUST ser visible en:
  - Plano de mesas (vista general y detalle).
  - Pantalla de Cocina (KDS).
  - Pantalla de Cobro (Caja).
  - Comprobante de pago (PDF).

### 3. Liberación en Dos Pasos (Flujo de Pago)
- Al presionar "Cobrar y Liberar", la mesa MUST cambiar al estado `POR_PAGAR`.
- El color visual para `POR_PAGAR` MUST ser Celeste (`info`).
- Mientras la mesa esté en `POR_PAGAR`, MUST estar bloqueada para añadir nuevos platos o abrir nuevas comandas.
- El estado `POR_PAGAR` MUST persistir hasta que la comanda asociada sea marcada como `COBRADA` en el módulo de Caja.
- Una vez procesado el pago, todas las mesas vinculadas a la comanda MUST volver al estado `LIBRE` (Verde).

## Escenarios

### Escenario: Crear pedido con múltiples mesas
- **Given** que el mozo está en la pantalla de "Nueva Comanda"
- **When** selecciona las mesas 5 y 6
- **And** ingresa el nombre "Familia González"
- **And** confirma el pedido con 2 platos
- **Then** el sistema MUST crear una única comanda vinculada a ambas mesas
- **And** ambas mesas MUST cambiar su estado a `OCUPADA`
- **And** el nombre "Familia González" MUST aparecer en el KDS para esas mesas.

### Escenario: Ver nombre de cliente en plano
- **Given** que la mesa 10 está ocupada por "Juan Pérez"
- **When** el mozo visualiza el plano de mesas
- **Then** la tarjeta de la mesa 10 MUST mostrar el texto "JUAN PÉREZ" en la parte inferior.

### Escenario: Flujo de Cobro y Liberación
- **Given** que la mesa 3 está `OCUPADA`
- **When** el mozo presiona "Cobrar y Liberar"
- **Then** la mesa 3 MUST cambiar a color celeste (`POR_PAGAR`)
- **And** el botón de liberación MUST quedar deshabilitado
- **And** al realizar el pago en Caja, la mesa 3 MUST volver automáticamente a `LIBRE` (Verde).
