# Spec: Sistema de Temas Dinámicos

## Visión General
El sistema permite el cambio global de tema (Claro/Oscuro) controlado exclusivamente por el administrador.

## Requerimientos

### 1. Control Centralizado
- Solo el usuario con rol `ADMIN` MAY cambiar el modo del sistema.
- El estado del tema MUST persistir en el modelo `ConfiguracionSistema`.

### 2. Reactividad UI
- Todos los componentes MUST usar variables CSS (`--primary`, `--surface`, etc.) definidas en `base.html`.
- No se permiten colores hardcoded (`#ffffff`, `bg-dark`, etc.) en los templates.
- El modo claro MUST cumplir con las guías WCAG de contraste.

### 3. Glassmorphism
- El efecto de desenfoque (`backdrop-blur`) MUST adaptarse dinámicamente.
- En modo claro, los fondos deben usar opacidades de blanco (`rgba(255,255,255,0.x)`).
- En modo oscuro, los fondos deben usar opacidades de negro o gris oscuro.

## Escenarios

### Escenario: Cambio de tema por Administrador
- **Given** que el administrador está en el panel de configuración
- **When** cambia el interruptor a "Modo Claro"
- **Then** todo el sistema (Login, KDS, Caja, Reportes) MUST actualizarse inmediatamente a la paleta clara.
- **And** los textos MUST cambiar a color oscuro (`on-surface`) para mantener contraste.
