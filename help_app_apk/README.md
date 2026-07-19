# TrazOp autónoma para Android

TrazOp ejecuta el backend Flask y su almacenamiento SQLite dentro del propio
celular. El WebView sólo puede navegar a `http://127.0.0.1:5000`, por lo que
esta versión de pruebas no depende de un PC, alojamiento externo ni internet.

El código Python, las plantillas y los recursos web se sincronizan desde la
raíz del proyecto durante la compilación. Las bases de datos del proyecto no
se empaquetan: una instalación nueva crea su almacenamiento privado usando
exclusivamente el esquema definido en `core/db.py`.

La configuración de publicación futura se conserva fuera del APK y no afecta
esta versión autónoma de pruebas.

## Compilar

```text
flutter pub get
flutter build apk --release --target-platform android-arm64
```

El APK incluye Flutter, Python 3.13, Flask y los recursos web de TrazOp. No
acepta una URL configurable ni permite navegar a servidores externos.
