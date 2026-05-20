# RestaurantOS

Sistema de Gestión de Restaurantes (Fullstack Django + PostgreSQL + Alpine.js).

## Despliegue en Railway (Producción)

Desplegar este proyecto en la nube usando [Railway.app](https://railway.app/) toma menos de 10 minutos. Sigue estos pasos:

### 1. Preparar la cuenta y el repositorio
1. Sube este código a un repositorio en tu cuenta de GitHub.
2. Crea una cuenta gratuita en [Railway.app](https://railway.app/).
3. Haz clic en **"New Project"** -> **"Deploy from GitHub repo"** y selecciona tu repositorio de RestaurantOS.

### 2. Agregar la Base de Datos PostgreSQL
1. En el panel de tu proyecto en Railway, haz clic en **"New"** (o en el botón "+").
2. Selecciona **"Database"** -> **"Add PostgreSQL"**.
3. Espera unos segundos a que se instale la base de datos.

### 3. Configurar Variables de Entorno
1. Haz clic en el servicio de tu código (el que está enlazado a GitHub).
2. Ve a la pestaña **"Variables"**.
3. Haz clic en **"New Variable"** y agrega exactamente estas 4 variables:
   - `DEBUG`: Escribe `False`
   - `SECRET_KEY`: Inventa una clave segura (ej: `h9823yr892y3fh823y`)
   - `ALLOWED_HOSTS`: Escribe `*`
   - `DATABASE_URL`: Haz clic en "Add Reference" o el ícono de llave mágica y selecciona `DATABASE_URL` del plugin de PostgreSQL que acabas de instalar.

### 4. Desplegar y Correr
1. Railway detectará los archivos `railway.toml` y `Procfile` y comenzará a compilar (Build).
2. Al finalizar, ejecutará automáticamente el script `deploy.sh` que hace tres cosas:
   - Migra la base de datos (`migrate`).
   - Recolecta los estáticos (`collectstatic`).
   - Puebla la base de datos inicial con `seed_data.py` (usuarios, mesas, menú).
3. ¡Listo! Ve a la pestaña **"Settings"**, genera un **Domain** público y abre la URL. 
   - Ingresa con usuario `admin` y contraseña `pass123`.
