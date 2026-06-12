# TrazOp de pruebas en Azure App Service

Esta configuracion publica TrazOp sin modificar la aplicacion de produccion en
PythonAnywhere. El plan F1 de Azure esta destinado a desarrollo y pruebas.

## Recursos

- App Service: Linux, Python 3.11, plan Free F1.
- Codigo: repositorio privado de GitHub.
- Datos: `/home/data/trazop-pruebas`.
- Inicio: `bash deploy/azure/startup.sh`.

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

En `Settings` > `Configuration` > `Startup Command`, usar:

```text
bash deploy/azure/startup.sh
```

## Conectar GitHub

1. Abrir `Deployment Center`.
2. Elegir `GitHub`.
3. Autorizar la cuenta y seleccionar:
   - Organization: la cuenta propietaria.
   - Repository: `HELP_APP_v1.0.0`.
   - Branch: `main`.
4. Guardar y esperar a que termine la primera publicacion.

## Base de datos de pruebas

La base nunca se sube al repositorio. Se copia de forma privada a:

```text
/home/data/trazop-pruebas/database.db
```

Antes de reemplazarla:

1. Detener temporalmente la Web App.
2. Guardar una copia de seguridad de la base remota.
3. Transferir una copia de `database.db`, no la base de produccion.
4. Iniciar la Web App.

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
