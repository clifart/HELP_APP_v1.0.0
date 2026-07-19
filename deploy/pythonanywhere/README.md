# Publicar TrazOp en PythonAnywhere

Con este despliegue el servidor queda en internet y el celular deja de depender
de VS Code, del PC y de la red Wi-Fi local.

## 1. Subir el codigo

Abre una consola Bash en PythonAnywhere y deja el proyecto, por ejemplo, en:

```text
/home/TU_USUARIO/HELP_APP
```

Crea el entorno e instala las dependencias:

```bash
cd /home/TU_USUARIO/HELP_APP
python3.13 -m venv /home/TU_USUARIO/.virtualenvs/trazop
/home/TU_USUARIO/.virtualenvs/trazop/bin/pip install -r requirements_server.txt
```

## 2. Crear la Web App

En **Web > Add a new web app** selecciona **Manual configuration** y la misma
version de Python del entorno. En **Virtualenv** escribe:

```text
/home/TU_USUARIO/.virtualenvs/trazop
```

Reemplaza el contenido del archivo WSGI que muestra PythonAnywhere por:

```python
import os
import sys

project_home = "/home/TU_USUARIO/HELP_APP"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ["HELP_APP_MASTER_KEY"] = "CAMBIA_ESTA_CLAVE_TECNICA"

from pythonanywhere_wsgi import application
```

No publiques la clave tecnica en el repositorio. El punto de entrada crea y
conserva automaticamente la clave privada de sesiones en `~/.trazop` y guarda
los datos persistentes en `~/trazop-data`.

En **Static files** configura:

```text
URL:       /static/
Directory: /home/TU_USUARIO/HELP_APP/static
```

Pulsa **Reload** y abre:

```text
https://TU_USUARIO.pythonanywhere.com/
```

## 3. Preparar el APK

Para dejar el dominio incorporado en el APK:

```bash
cd help_app_apk
flutter pub get
flutter build apk --release --dart-define=HELP_APP_URL=https://TU_USUARIO.pythonanywhere.com/
```

El archivo instalable queda en:

```text
help_app_apk/build/app/outputs/flutter-apk/app-release.apk
```

Si se compila sin `HELP_APP_URL`, el celular pedira el usuario de
PythonAnywhere la primera vez y lo conservara. Ambas opciones funcionan sin el
PC encendido.

## Actualizaciones

Tras subir cambios al codigo, instala dependencias solo si cambio el archivo de
requisitos y pulsa **Reload** en la pestaña Web. No es necesario recompilar el
APK mientras el dominio siga siendo el mismo.
