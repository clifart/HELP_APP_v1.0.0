import sqlite3

conn = sqlite3.connect("database.db")
cur = conn.cursor()

# Mostrar columnas existentes
cur.execute("PRAGMA table_info(tareas)")
columnas = [c[1] for c in cur.fetchall()]
print("📋 Columnas actuales:", columnas)

# Agregar las columnas si no existen
if "hora_inicio" not in columnas:
    cur.execute("ALTER TABLE tareas ADD COLUMN hora_inicio TEXT")
    print("✅ Columna 'hora_inicio' creada.")

if "hora_fin" not in columnas:
    cur.execute("ALTER TABLE tareas ADD COLUMN hora_fin TEXT")
    print("✅ Columna 'hora_fin' creada.")

conn.commit()
conn.close()
print("🎯 Base de datos actualizada correctamente.")
