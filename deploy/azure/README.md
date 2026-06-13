# TrazOp de pruebas en Azure App Service

Esta configuracion publica TrazOp sin modificar la aplicacion de produccion en
PythonAnywhere. El plan F1 de Azure esta destinado a desarrollo y pruebas.

## Recursos

- App Service: Linux, Python 3.11, plan Free F1.
- Codigo: despliegue directo con Azure CLI.
- Datos: `/home/data/trazop-pruebas-v1`.
- Inicio: Gunicorn configurado directamente en App Service.

El directorio `/home` es persistente entre reinicios. No guardar la base de
datos dentro de `/home/site/wwwroot`, porque una publicacion puede reemplazar
el codigo de esa carpeta.

## Crear la aplicacion

1. Entrar en `https://portal.azure.com/`.
2. Buscar `App Services` y seleccionar `Create` > `Web App`.
3. Usar estos valores:
   - Publish: `Code`
   - Runtime stack: `Python 3.11`
   - Operating System: `Linux`
   - Pricing plan: `Free F1`
4. Elegir un nombre unico, por ejemplo `trazop-pruebas-usuario`.
5. Crear el recurso.

## Variables de entorno

En `Settings` > `Environment variables`, agregar:

```text
HELP_APP_DATA_DIR=/home/data/trazop-pruebas
HELP_APP_SECRET_KEY=<clave-aleatoria-larga>
HELP_APP_MASTER_KEY=<clave-tecnica-privada>
HELP_APP_HTTPS=1
HELP_APP_ENABLE_AUTOCIERRE=1
SCM_DO_BUILD_DURING_DEPLOYMENT=true
```

No publicar los valores de las claves en GitHub.

En `Settings` > `Stack settings` > `Startup Command`, usar:

```text
gunicorn --bind=0.0.0.0:8000 --workers 1 --threads 4 --timeout 120 --access-logfile - --error-logfile - wsgi:app
```

## Publicar el codigo

GitHub Actions puede quedar bloqueado por la configuracion de facturacion de
GitHub, incluso cuando Azure usa el plan gratuito. El despliegue directo evita
esa dependencia.

Desde PowerShell, con Azure CLI instalado:

```powershell
az login --use-device-code
git archive --format=zip --output="$env:TEMP\trazop-azure.zip" HEAD
az webapp deploy `
  --resource-group trazop-pruebas-rg `
  --name trazop-pruebas-2026 `
  --src-path "$env:TEMP\trazop-azure.zip" `
  --type zip `
  --clean true `
  --restart true `
  --timeout 900000
```

## Base de datos de pruebas

La base nunca se sube al repositorio. Se copia de forma privada a una carpeta
versionada, por ejemplo:

```text
/home/data/trazop-pruebas-v1/database.db
```

Antes de reemplazarla:

1. Crear una copia consistente de `database.db`.
2. Transferirla con `--type static`, `--clean false` y una ruta nueva.
3. Cambiar `HELP_APP_DATA_DIR` a la carpeta nueva.
4. Reiniciar la Web App y verificar el ingreso.

Ejemplo:

```powershell
az webapp deploy `
  --resource-group trazop-pruebas-rg `
  --name trazop-pruebas-2026 `
  --src-path "$env:TEMP\trazop-pruebas-database.db" `
  --type static `
  --target-path /home/data/trazop-pruebas-v2/database.db `
  --clean false `
  --restart false

az webapp config appsettings set `
  --resource-group trazop-pruebas-rg `
  --name trazop-pruebas-2026 `
  --settings HELP_APP_DATA_DIR=/home/data/trazop-pruebas-v2

az webapp restart `
  --resource-group trazop-pruebas-rg `
  --name trazop-pruebas-2026
```

## APK

Cuando la URL HTTPS funcione, compilar:

```text
flutter build apk --release --dart-define=HELP_APP_URL=https://NOMBRE.azurewebsites.net/
```

El APK resultante queda en:

```text
help_app_apk/build/app/outputs/flutter-apk/app-release.apk
```

## Limitaciones del plan F1

- Es para pruebas, sin garantia de disponibilidad.
- Incluye 60 minutos de CPU al dia y 1 GB de almacenamiento.
- Puede suspenderse por inactividad y tardar unos segundos en reactivarse.
- El autocierre se ejecuta al arrancar y cada 10 segundos mientras la
  aplicacion esta activa. Si Azure la suspende, recupera los cierres vencidos
  al reactivarse.
