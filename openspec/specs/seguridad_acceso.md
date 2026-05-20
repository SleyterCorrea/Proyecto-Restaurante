# Spec: Seguridad y UX de Acceso (Login)

## Visión General
Define los estándares de seguridad visual y experiencia de usuario para la puerta de entrada al sistema (Login).

## Requerimientos

### 1. Estética Visual
- La página de login MUST implementar un diseño de "Frosted Glass" (Glassmorphism) con un desenfoque (`backdrop-filter: blur()`) mínimo de 15px.
- La tarjeta de login MUST tener una opacidad máxima del 40% para permitir la visualización del fondo decorativo.
- Todos los iconos y etiquetas MUST tener un contraste alto (Blanco con opacidad 80% o superior) para asegurar legibilidad.

### 2. Funcionalidad de Contraseña
- El campo de contraseña MUST incluir un botón de alternancia ("Toggle") con un icono de ojo.
- Al presionar el icono, el sistema MUST cambiar dinámicamente el tipo de input entre `password` y `text`.
- Por seguridad, el campo MUST iniciarse siempre en modo `password`.

### 3. Capas y Jerarquía (Z-Index)
- Los iconos decorativos dentro de los inputs (persona, candado) MUST estar posicionados siempre por encima de cualquier fondo decorativo (`z-index` superior) para evitar que se oculten al interactuar con el campo.
