# Union-Mesas Specification

## Purpose
Define la lógica de negocio para la unión física y lógica de múltiples mesas bajo una misma orden de servicio.

## Requirements

### Requirement: Límite de Unión
El sistema MUST permitir unir hasta un máximo de 3 mesas por cada comanda.

#### Scenario: Selección de 2 mesas
- GIVEN un mozo en el selector de mesas
- WHEN selecciona la Mesa 1 y la Mesa 2
- THEN el sistema DEBE permitir la selección de ambas.

#### Scenario: Intento de exceder el límite
- GIVEN un mozo ha seleccionado 3 mesas
- WHEN intenta seleccionar una cuarta mesa
- THEN el sistema DEBE bloquear la selección
- AND DEBE mostrar una alerta: "Límite máximo de 3 mesas alcanzado".

### Requirement: Ocupación Atómica
Al confirmar un pedido con mesas unidas, todas las mesas involucradas MUST cambiar su estado a `OCUPADA`.

#### Scenario: Confirmación de comanda unida
- GIVEN un pedido configurado con Mesas 1, 2 y 3
- WHEN el mozo presiona "Confirmar Pedido"
- THEN se DEBE crear la comanda
- AND las Mesas 1, 2 y 3 DEBEN aparecer como "Ocupada" en el plano general.

### Requirement: Liberación Grupal
La liberación de la mesa principal o cualquier mesa vinculada MUST disparar la liberación de todo el grupo.

#### Scenario: Cierre de comanda unida
- GIVEN una comanda activa vinculada a las Mesas 1 y 2
- WHEN el cajero o mozo libera la Mesa 1
- THEN la comanda se DEBE marcar como lista/cobrada
- AND tanto la Mesa 1 como la Mesa 2 DEBEN pasar al estado `LIBRE`.

### Requirement: Visualización de Unión
El plano de mesas SHOULD indicar visualmente qué mesas están trabajando en conjunto.

#### Scenario: Polling de estado actual
- GIVEN una comanda uniendo las mesas 5 y 6
- WHEN el sistema realiza el polling de estado
- THEN ambas mesas DEBEN mostrar la misma información de comanda (Mozo, Total, Tiempo).
