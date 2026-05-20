# Spec: Gestión de Personal y Trabajadores

## Visión General
Este módulo permite al administrador gestionar el equipo del restaurante, definiendo identidades legales (DNI), tipos de contrato y acceso al sistema mediante roles.

## Requerimientos

### 1. Datos del Trabajador
- El sistema MUST almacenar los siguientes datos obligatorios para cada trabajador:
  - Nombres y Apellidos.
  - DNI / Documento de Identidad (Único).
  - Nombre de Usuario (Para login).
  - Rol (Admin, Mozo, Cocinero, Cajero).
  - Tipo de Trabajo (Full Time / Part Time).
  - Fecha de Ingreso.
- El sistema MUST permitir almacenar opcionalmente la Fecha de Término de Contrato.

### 2. Seguridad y Acceso
- El administrador MUST ser el único con permisos para crear, editar o desactivar trabajadores.
- Al registrar o editar un trabajador, el sistema MUST permitir definir una contraseña.
- Las contraseñas MUST almacenarse siempre mediante hashing seguro.
- Si al editar un trabajador se deja el campo de contraseña en blanco, el sistema MUST mantener la contraseña anterior.

### 3. Interfaz de Administración
- El sistema MUST proveer una tabla con búsqueda en tiempo real por nombre, apellidos o DNI.
- La interfaz MUST seguir los estándares de diseño "Dark Glassmorphism" del sistema.
- El Admin MUST tener un acceso directo ("Personal") en la barra de navegación global.

## Escenarios

### Escenario: Registrar un nuevo Mozo
- **Given** que el administrador está en el panel de Gestión de Personal
- **When** presiona "Registrar Trabajador"
- **And** completa los datos personales y asigna el rol "MOZO"
- **And** define el tipo de contrato como "PART TIME"
- **And** guarda los cambios
- **Then** el nuevo trabajador MUST aparecer inmediatamente en la lista
- **And** podrá iniciar sesión para acceder únicamente a las funciones de mesero.

### Escenario: Editar contrato de un trabajador
- **Given** que un trabajador cambia de Part Time a Full Time
- **When** el administrador edita su perfil
- **And** cambia el "Tipo de Trabajo" a "FULL TIME"
- **And** guarda sin modificar la contraseña
- **Then** el sistema MUST actualizar el tipo de contrato
- **And** la contraseña de acceso del trabajador MUST permanecer igual.
