# TrazOp en PythonAnywhere

Esta configuración describe cómo desplegar TrazOp en PythonAnywhere.
PythonAnywhere ofrece un entorno Python gestionado que puede ejecutar Flask
y almacenará los datos persistentes en tu directorio `/home/<usuario>`.

## Requisitos previos

- Cuenta en https://www.pythonanywhere.com/
- Python 3.11 disponible en tu cuenta
- Repositorio clonado o copiado en tu directorio de usuario
  (por ejemplo `/home/<usuario>/HELP_APP_v1.0.0`)

## Pasos de despliegue

1. En PythonAnywhere, crea un nuevo "Web app".
2. Selecciona "Manual configuration" y elige Python 3.11.
3. En la pestaña "Web" configura:
   - Source code: `/home/<usuario>/HELP_APP_v1.0.0`
   - Virtualenv: `/home/<usuario>/.virtualenvs/help_app` o similar
   - WSGI configuration file: editar según los pasos siguientes

## Configurar virtualenv

En la consola de PythonAnywhere ejecuta:

```bash
python3.11 -m venv ~/.virtualenvs/help_app
source ~/.virtualenvs/help_app/bin/activate
pip install -r ~/HELP_APP_v1.0.0/requirements.txt
```

> Si tu cuenta no tiene `python3.11`, usa la versión disponible más cercana.

## Configurar el archivo WSGI

Edita el archivo WSGI que creó PythonAnywhere y reemplaza su contenido por:

```python
import sys
import os

project_home = '/home/<usuario>/HELP_APP_v1.0.0'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ['PYTHONPATH'] = project_home

from app import app as application
```

## Variables de entorno

En la pestaña "Web" de PythonAnywhere, agrega estas variables en "Environment
django or flask app settings" (o similar):

```text
HELP_APP_DATA_DIR=/home/<usuario>/help_app_data
HELP_APP_SECRET_KEY=<clave-aleatoria-larga>
HELP_APP_MASTER_KEY=<clave-tecnica-privada>
HELP_APP_HTTPS=1
HELP_APP_ENABLE_AUTOCIERRE=1
```

- `HELP_APP_DATA_DIR` es la carpeta donde se guardará `database.db` y otros
  archivos persistentes.
- En PythonAnywhere, `/home/<usuario>` es persistente, por lo que es una buena
  ubicación para `HELP_APP_DATA_DIR`.

## Crear la carpeta de datos persistentes

En la consola de PythonAnywhere ejecuta:

```bash
mkdir -p /home/<usuario>/help_app_data
ls -ld /home/<usuario>/help_app_data
```

Si tienes una base de datos inicial, copia `database.db` a esa carpeta:

```bash
cp ~/HELP_APP_v1.0.0/database.db /home/<usuario>/help_app_data/database.db
```

## Reiniciar la aplicación

Después de instalar dependencias y configurar el WSGI, guarda los cambios y
pulsa "Reload" en la pestaña Web.

## APK y URL del servidor

Para compilar el APK móvil que apunte a PythonAnywhere, usa:

```bash
flutter build apk --release --dart-define=HELP_APP_URL=https://<usuario>.pythonanywhere.com/
```

También puedes cambiar la URL directamente en la app desde el botón de
configuración del WebView.

## Notas importantes

- PythonAnywhere puede suspender la app por inactividad si usas el plan
  gratuito.
- Asegúrate de no guardar la base de datos en el directorio de código si
  planeas actualizar el repositorio.
- La app ya soporta `HELP_APP_DATA_DIR`, así que puedes apuntar los datos a
  una ruta persistente independiente del código.
