import os
import shutil

def listar_backups(backups_dir):
    if not os.path.exists(backups_dir):
        print("⚠️ No existe la carpeta 'backups'. Aún no has creado copias.")
        return []

    backups = [d for d in os.listdir(backups_dir) if d.startswith('HELP_APP_BACKUP_')]
    backups.sort(reverse=True)
    return [os.path.join(backups_dir, b) for b in backups]

def restaurar_backup(origen, base_dir):
    print(f"🔁 Restaurando desde: {origen}\n")

    for item in os.listdir(origen):
        src = os.path.join(origen, item)
        dst = os.path.join(base_dir, item)

        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)

    print("✅ Restauración completada correctamente.")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    backups_dir = os.path.join(base_dir, 'backups')

    backups = listar_backups(backups_dir)
    if not backups:
        print("⚠️ No hay copias de seguridad disponibles.")
    else:
        print("Copias de seguridad disponibles:")
        for i, b in enumerate(backups):
            print(f"{i+1}. {os.path.basename(b)}")

        seleccion = input("\nSelecciona el número del backup a restaurar: ")
        try:
            indice = int(seleccion) - 1
            if 0 <= indice < len(backups):
                restaurar_backup(backups[indice], base_dir)
            else:
                print("❌ Opción no válida.")
        except ValueError:
            print("❌ Entrada inválida.")

    input("\nPresiona ENTER para salir...")
