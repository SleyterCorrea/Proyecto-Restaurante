# Sistema de Gestión de Restaurante

Sistema web desarrollado en Django para gestionar las operaciones de un restaurante: mesas, pedidos, cocina, caja, inventario y reportes. Proyecto grupal universitario.

---

## ¿Qué hace el sistema?

El restaurante necesitaba digitalizar su operación. Este sistema cubre todo el flujo desde que el cliente se sienta hasta que paga:

- El **mesero** ve el plano de mesas, toma el pedido y lo manda a cocina
- La **cocina** recibe las comandas en tiempo real y marca qué está listo
- El **cajero** cobra, abre y cierra turno
- El **administrador** gestiona el menú, inventario, personal y ve reportes

---

## Módulos

| Módulo | Qué hace |
|--------|----------|
| `usuarios` | Registro, login y roles (Admin, Mesero, Cocinero, Cajero) |
| `mesas` | Plano de mesas por zonas, estados y unión de mesas |
| `comandas` | Creación y seguimiento de pedidos |
| `menu` | Gestión de platos, categorías y precios |
| `cocina` | KDS (pantalla de cocina) con WebSockets |
| `caja` | Apertura/cierre de turno y cobro de comandas |
| `inventario` | Control de insumos, stock y órdenes de compra |
| `reportes` | Ventas por período, platos más vendidos, rendimiento |
| `notificaciones` | Alertas en tiempo real entre roles |

---

## Tecnologías usadas

- **Python / Django 4.2**
- **Django REST Framework** — API para el frontend
- **Django Channels + Daphne** — WebSockets para cocina y notificaciones en tiempo real
- **JWT** — Autenticación con tokens
- **PostgreSQL** — Base de datos en producción
- **SQLite** — Para desarrollo local
- **ReportLab** — Generación de PDFs para reportes
- **Docker** — Para despliegue
- **Railway** — Plataforma de hosting

---

## Cómo correrlo en local

### Requisitos previos
- Python 3.11+
- Git

### Pasos

```bash
# 1. Clonar el repo
git clone https://github.com/SleyterCorrea/Proyecto-Restaurante.git
cd Proyecto-Restaurante

# 2. Crear entorno virtual
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Copiar variables de entorno
copy .env.example .env
# Editar .env con tus datos

# 5. Aplicar migraciones
python manage.py migrate

# 6. Cargar datos de prueba (opcional)
python seed_data.py

# 7. Correr el servidor
python manage.py runserver
```

Abrir en el navegador: `http://127.0.0.1:8000`

---

## Variables de entorno (.env)

```
SECRET_KEY=tu_clave_secreta
DEBUG=True
DATABASE_URL=sqlite:///db.sqlite3
```

Ver `.env.example` para la lista completa.

---

## Flujo de trabajo en equipo

Cada integrante trabaja en su propia rama:

```bash
# Desde main, crear tu rama
git checkout main
git pull origin main
git checkout -b tu-nombre

# Trabajar... y subir cambios
git add .
git commit -m "descripción de lo que hiciste"
git push origin tu-nombre
```

Para integrar cambios al proyecto general se hace un Pull Request hacia `main`.

---

## Estructura del proyecto

```
Proyecto-Restaurante/
├── apps/
│   ├── caja/
│   ├── comandas/
│   ├── inventario/
│   ├── menu/
│   ├── mesas/
│   ├── notificaciones/
│   ├── reportes/
│   └── usuarios/
├── restaurant/        # Configuración principal de Django
├── templates/         # HTML por módulo
├── static/            # CSS y JS
├── tests/             # Pruebas automatizadas
├── manage.py
└── requirements.txt
```

---

## Equipo

Proyecto desarrollado como trabajo grupal — cada integrante tiene su rama con su parte del sistema.
 
