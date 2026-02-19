# RESUMEN TECNICO - HELP_APP

Fecha de corte: 2026-02-18

## 1) Vision general
HELP_APP es una aplicacion web interna para control operativo de ordenes de produccion (OP) y seguimiento de tareas por proceso.
El sistema separa dos roles:
- Admin: crea usuarios, crea/cierra OP maestras, revisa historial y ejecuta funciones tecnicas.
- Usuario: toma procesos por OP, registra tiempos, pausa/reanuda, completa checklist y finaliza tareas.

El backend esta implementado en Flask con SQLite como base de datos local, orientado a despliegue en red LAN y empaquetado en .exe con PyInstaller.

## 2) Arquitectura actual
- Entrada principal: `app.py`
  - Inicializa Flask, esquema minimo de BD, blueprints y login.
  - Inicia hilo de autocierre cada 60 segundos.
  - Soporta acceso por IP LAN (`0.0.0.0:5000`).
- Blueprint Admin: `admin/views.py`
  - Gestion de usuarios y OP.
  - Historial general, carpeta diaria, exportaciones y modo tecnico.
- Blueprint Usuario: `usuario/views.py`
  - Inicio de procesos por OP.
  - Reglas de dependencia por impresion.
  - Checklist por modulo.
  - Pausa/reanudar/finalizar/autocierre por tarea.
- Capa Core:
  - `core/db.py`: conexion y migraciones base de `tareas`.
  - `core/horarios.py`: ventanas laborales por turno diurno/nocturno.
  - `core/auto_cierre.py`: cierre automatico y registro en historial.
  - `core/registro_diario.py`: escritura de trazabilidad diaria en Excel.
  - `core/exportar_excel.py`: exporta tablas SQLite a xlsx.

## 3) Modelo de datos (estado real observado)
Base analizada: `database.db`.
Tablas detectadas: `usuarios`, `tareas`, `historial_tareas`, `checklist_modulos`, `checklist_impresion`, `historial_mensual`, `registro_excel_log`, `ops_catalog`, `tareas_asignadas`.

Volumen actual (2026-02-18):
- `usuarios`: 26
- `tareas`: 643
- `historial_tareas`: 564
- `checklist_modulos`: 470
- `checklist_impresion`: 248
- `registro_excel_log`: 417
- `historial_mensual`: 1

## 4) Flujo operativo principal
1. Admin crea OP maestra activa.
2. Usuario selecciona OP + proceso.
3. El sistema valida reglas de negocio:
   - CORTE se permite siempre.
   - Procesos no impresion exigen condicion sobre impresion (finalizada o confirmada).
4. Usuario ejecuta tarea con cronometraje real (inicio, pausa, reanudacion).
5. Antes de finalizar, debe completar checklist de modulo (excepto procesos exentos).
6. Al finalizar:
   - actualiza `tareas` a `Finalizado`;
   - inserta en `historial_tareas`;
   - registra token en `registro_excel_log` para evitar duplicados;
   - escribe fila en diario Excel.

## 5) Enfoque funcional y operativo
HELP_APP prioriza control de piso de produccion con estas decisiones:
- Regla de secuencia por impresion para evitar arranques fuera de orden.
- Cierre automatico por tiempo laboral (8h), con soporte de horario extendido.
- Trazabilidad dual: SQLite transaccional + salida operativa diaria en Excel.
- Modo tecnico para soporte (limpieza demo, backups, test de autocierre, reset de claves).

## 6) Seguridad y control de acceso
- Autenticacion por usuario/clave con hash (Werkzeug), con compatibilidad a legados en texto plano.
- Roles por sesion (`admin` / `usuario`) y rutas protegidas por blueprint.
- Flujo de primer ingreso y cambio obligatorio tras reset (`must_change_password`).

## 7) Fortalezas tecnicas
- Bajo costo operativo: stack liviano Flask + SQLite.
- Portabilidad alta para LAN y entorno offline.
- Buena trazabilidad de ejecucion real por tarea.
- Reglas de negocio claras para dependencia de procesos.
- Capacidades de soporte incluidas (modo tecnico y pruebas de autocierre).

## 8) Riesgos y deuda tecnica observada
- Valores sensibles hardcodeados (`secret_key`, `MASTER_KEY`, `CLAVE_TECNICA`) en codigo fuente.
- `app.py` y vistas concentran mucha logica de negocio (baja modularidad).
- Desalineacion de esquema heredado en `tareas` (columnas legacy coexistentes).
- Inconsistencia de import en record mensual:
  - `admin/views.py` importa `generar_record_mensual` desde `core.db`,
  - pero la funcion vive en `core/record_mensual.py`.
- Falta una suite de pruebas automatizadas integral (existe prueba puntual de autocierre).

## 9) Proyeccion recomendada (90 dias)
Fase 1 (0-30 dias): Estabilizacion
- Centralizar secretos en variables de entorno.
- Corregir import de record mensual y estandarizar migraciones de esquema.
- Definir respaldo automatizado de `database.db` y `HELP_APP_TAREAS_DIARIAS`.

Fase 2 (31-60 dias): Calidad tecnica
- Extraer reglas de negocio a servicios (`services/`).
- Agregar pruebas unitarias para validaciones de flujo y autocierre.
- Crear auditoria minima de eventos criticos (login, cierre, reset).

Fase 3 (61-90 dias): Escalabilidad funcional
- API interna para dashboards (productividad, tiempos muertos, cumplimiento checklist).
- Tablero de KPIs por OP/proceso/usuario.
- Preparar paso opcional de SQLite a PostgreSQL sin romper UI actual.

## 10) Conclusiones
HELP_APP ya cubre el ciclo operativo esencial de planta: planificar OP, ejecutar por proceso y cerrar con trazabilidad.
El enfoque correcto para crecer no es reescribir, sino fortalecer seguridad, modularidad y observabilidad.
Con una hoja de ruta incremental, el sistema puede evolucionar de herramienta operativa local a plataforma de control productivo con indicadores en tiempo real.
