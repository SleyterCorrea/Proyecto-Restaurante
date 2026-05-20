# Módulo de Caja, Facturación e Historial de Ventas

## 1. Visión General
El módulo de Caja gestiona el flujo final de las comandas, procesando los pagos, generando comprobantes físicos/digitales y manteniendo un registro auditable (Historial de Ventas) accesible bajo permisos específicos.

## 2. Requerimientos Cumplidos

### 2.1 Generación de Boleta Electrónica (PDF)
- **Diseño Profesional**: Formato estilo ticket que incluye el nombre del restaurante ("RESTAURANT OS"), ubicación de la mesa/zona, nombre del cliente y del mozo que atendió.
- **Validación de Tiempos**: Renderiza la fecha y hora exacta de la transacción en tiempo real utilizando la zona horaria local (`America/Lima`).
- **Desglose de Montos**: Calcula y muestra el subtotal, el IGV (10%) y el monto total final.
- **Conversión de Números a Letras**: Incorpora el apartado "SON:" con el monto final escrito en texto.
- **Tecnología Interactiva**: Incluye un código QR dinámico al pie del ticket que apunta a la URL original de la boleta para verificación.

### 2.2 Historial de Ventas Integrado
- **Interfaz Unificada**: El historial de ventas está embebido dentro del mismo módulo de Caja (`cobrar.html`) mediante un sistema de pestañas (Tabs) gestionado por Alpine.js, evitando recargas de página.
- **Seguridad por Roles (Backend)**:
  - **CAJERO**: Forzado a visualizar únicamente las transacciones del día actual local. No se muestran selectores de fecha en la UI.
  - **ADMIN**: Posee acceso a selectores de `Fecha Inicio` y `Fecha Fin` para realizar consultas históricas completas a la base de datos.
- **Datos Mostrados**: ID del pago, Fecha/Hora, Cliente, Ubicación (Mesa/Zona), Método de Pago, Monto Total, y acción rápida para descargar el ticket PDF generado.

### 2.3 Micro-interacciones (Mozo y UX)
- **Modificación Rápida de Pedidos**: En la vista de "Pedido Actual" del mozo, se integra un botón individual para eliminar por completo un plato del carrito, sin necesidad de vaciar todo el pedido ni utilizar el control de cantidad de uno en uno.
- **Sincronización WebSockets**: Normalización del rol del trabajador (`{{ user.rol.nombre|upper }}`) para asegurar que las notificaciones "Comida Lista" lleguen sin fallos de validación (soporta "MOZO" y "MESERO").

## 3. Modelo de Datos y Endpoints
- **API `GET /caja/api/historial/`**: Retorna el JSON de pagos. Acepta `fecha_inicio` y `fecha_fin`.
- **Vista PDF `/caja/boleta/<id>/`**: Utiliza ReportLab para construir el ticket al vuelo consultando los datos del modelo `Pago` y su relación `Comanda`.
