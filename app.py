import os
import sys
import socket
import threading
import webbrowser

from flask import Flask, request
from core.db import ensure_schema  # solo esto desde core.db aquí


# Intentamos importar la carpeta diaria; si falla, no rompemos la app
try:
    from core.registro_diario import get_carpeta_diaria  # carpeta diaria
except Exception as e:
    print(f"[WARN] No se pudo importar get_carpeta_diaria: {e}")

    def get_carpeta_diaria():
        return None

try:
    from core.historial_central import ejecutar_mantenimiento_mensual_historial
except Exception as e:
    print(f"[WARN] No se pudo importar mantenimiento mensual de historial: {e}")

    def ejecutar_mantenimiento_mensual_historial(*args, **kwargs):
        return {"ejecutado": False, "motivo": "no_disponible"}


def _resource_path(rel_path: str) -> str:
    """
    Devuelve la ruta correcta a recursos tanto en desarrollo como en .exe (PyInstaller).
    - En .exe onefile, PyInstaller extrae a sys._MEIPASS.
    - En desarrollo, usa la carpeta del proyecto.
    """
    base = getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(__file__)))
    return os.path.join(base, rel_path)


def _ip_lan() -> str:
    """
    Obtiene la IP LAN del PC (Wi-Fi) sin depender de internet.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # no requiere que haya internet, solo selecciona interfaz
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def _port_ocupado(host: str, port: int) -> bool:
    """
    Devuelve True si hay algo escuchando en host:port.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.25)
    try:
        return s.connect_ex((host, port)) == 0
    finally:
        try:
            s.close()
        except Exception:
            pass


def create_app():
    # Forzar rutas de templates/static para que funcionen en .exe
    app = Flask(
        __name__,
        template_folder=_resource_path("templates"),
        static_folder=_resource_path("static"),
    )

    app.secret_key = "cambia-esta-clave-super-secreta"
    app.config["MASTER_KEY"] = "HELPAPP_2025"
    app.config.setdefault("DEBUG_AVISO_SEG", 0)

    # =========================
    # ESQUEMA / BASE DE DATOS
    # =========================
    ensure_schema()
    try:
        ejecutar_mantenimiento_mensual_historial()
    except Exception as e:
        print(f"[WARN] No se pudo ejecutar mantenimiento mensual de historial: {e}")

    @app.before_request
    def _mantenimiento_historial_fin_mes():
        # Evita trabajo extra para peticiones de archivos estáticos.
        if request.endpoint == "static":
            return None
        try:
            ejecutar_mantenimiento_mensual_historial()
        except Exception as e:
            print(f"[WARN] Mantenimiento mensual de historial omitido: {e}")
        return None

    # =========================
    # BLUEPRINTS
    # =========================
    from admin import admin_bp
    from usuario import usuario_bp

    app.register_blueprint(admin_bp)
    app.register_blueprint(usuario_bp)

    # =========================
    # CARPETA DIARIA (AL CREAR LA APP)
    # =========================
    try:
        carpeta = get_carpeta_diaria()
        if carpeta:
            print(f"Carpeta diaria lista: {carpeta}")
        else:
            print("[WARN] get_carpeta_diaria() devolvió None.")
    except Exception as e:
        print(f"[WARN] No se pudo preparar la carpeta diaria: {e}")

        # =========================
    # LOGIN
    # =========================
    @app.route("/", methods=["GET", "POST"])
    def login():
        from flask import render_template, request, redirect, url_for, session, flash
        from core.db import get_db_connection
        from werkzeug.security import check_password_hash

        if request.method == "POST":
            nombre = (request.form.get("nombre") or "").strip()
            contrasena = (request.form.get("contrasena") or "").strip()

            if not nombre or not contrasena:
                flash("Por favor completa todos los campos", "warning")
                return redirect(url_for("login"))

            conn = get_db_connection()
            cur = conn.cursor()

            user = cur.execute(
                "SELECT * FROM usuarios WHERE nombre = ?",
                (nombre,),
            ).fetchone()

            if not user:
                conn.close()
                flash("Usuario o contraseña incorrectos", "danger")
                return redirect(url_for("login"))

            stored = user["contrasena"]

            # PRIMER INGRESO (cuando la contraseña está vacía)
            if stored is None or str(stored).strip() == "":
                session["primer_ingreso_id"] = user["id"]
                session["primer_ingreso_nombre"] = user["nombre"]
                conn.close()
                return redirect(url_for("primer_ingreso"))

            # LOGIN NORMAL
            valid = False
            try:
                valid = check_password_hash(stored, contrasena) or (stored == contrasena)
            except Exception:
                valid = (stored == contrasena)

            if not valid:
                conn.close()
                flash("Usuario o contraseña incorrectos", "danger")
                return redirect(url_for("login"))

            # ✅ Login correcto
            session["usuario"] = user["nombre"]
            session["usuario_id"] = user["id"]  # ✅ clave para el flujo de cambio

            rol_raw = user["rol"] or ""
            session["rol"] = (
                "admin"
                if rol_raw.lower().strip() in ("admin", "administrador")
                else "usuario"
            )

            # ✅ OBLIGAR CAMBIO DE CONTRASEÑA SI VIENE DE RESET
            if int(user["must_change_password"] or 0) == 1:
                conn.close()
                return redirect("/cambiar_password")

            conn.close()

            if session["rol"] == "admin":
                return redirect(url_for("admin.panel"))
            return redirect(url_for("usuario.panel"))

        # GET: mostrar combo de usuarios
        conn = get_db_connection()
        usuarios = conn.execute("SELECT nombre, rol FROM usuarios").fetchall()
        conn.close()
        return render_template("login.html", usuarios=usuarios)

        # =========================
    # CAMBIO DE CONTRASEÑA OBLIGATORIO (DESPUÉS DE RESET)
    # =========================
    @app.route("/cambiar_password", methods=["GET", "POST"])
    def cambiar_password():
        from flask import request, session, redirect, url_for
        from core.db import get_db_connection
        from werkzeug.security import generate_password_hash

        # Sin sesión: vuelve al login
        if not session.get("usuario_id"):
            return redirect(url_for("login"))

        user_id = session["usuario_id"]

        conn = get_db_connection()
        cur = conn.cursor()

        row = cur.execute(
            "SELECT must_change_password FROM usuarios WHERE id=?",
            (user_id,),
        ).fetchone()

        if not row:
            conn.close()
            return redirect(url_for("login"))

        # Si ya no está obligado, vuelve al panel según rol (ENDPOINTS REALES)
        if int(row["must_change_password"] or 0) == 0:
            conn.close()
            if session.get("rol") == "admin":
                return redirect(url_for("admin.panel"))
            return redirect(url_for("usuario.panel"))

        # POST: guardar nueva contraseña
        if request.method == "POST":
            nueva = (request.form.get("nueva") or "").strip()
            confirmar = (request.form.get("confirmar") or "").strip()

            if len(nueva) < 4:
                conn.close()
                return "<h3>⚠️ Min 4 caracteres</h3><a href='/cambiar_password'>Volver</a>", 400

            if nueva != confirmar:
                conn.close()
                return "<h3>⚠️ No coinciden</h3><a href='/cambiar_password'>Volver</a>", 400

            if nueva == "1234":
                conn.close()
                return "<h3>⚠️ No puedes dejar 1234</h3><a href='/cambiar_password'>Volver</a>", 400

            # Guardar hash scrypt (igual que tu reset)
            hashed = generate_password_hash(nueva, method="scrypt")

            cur.execute(
                "UPDATE usuarios SET contrasena=?, must_change_password=0 WHERE id=?",
                (hashed, user_id),
            )
            conn.commit()
            conn.close()

            # Listo: vuelve al panel real
            if session.get("rol") == "admin":
                return redirect(url_for("admin.panel"))
            return redirect(url_for("usuario.panel"))

        conn.close()

        # GET: formulario simple (sin template, no rompe nada)
        return """
        <div style="max-width:420px;margin:30px auto;font-family:Arial;padding:18px;border:1px solid #ddd;border-radius:12px;">
          <h3>Crear nueva contraseña</h3>
          <p>Debes definir una nueva contraseña para continuar.</p>
          <form method="post">
            <div style="margin-bottom:10px;">
              <label>Nueva contraseña</label><br>
              <input type="password" name="nueva" required style="width:100%;padding:10px;">
            </div>
            <div style="margin-bottom:14px;">
              <label>Confirmar contraseña</label><br>
              <input type="password" name="confirmar" required style="width:100%;padding:10px;">
            </div>
            <button type="submit" style="width:100%;padding:10px;">Guardar</button>
          </form>
        </div>
        """





    # =========================
    # PRIMER INGRESO
    # =========================
    @app.route("/primer_ingreso", methods=["GET", "POST"])
    def primer_ingreso():
        from flask import render_template, request, redirect, url_for, session, flash
        from core.db import get_db_connection
        from werkzeug.security import generate_password_hash

        user_id = session.get("primer_ingreso_id")
        nombre = session.get("primer_ingreso_nombre")

        if not user_id:
            flash("Sesión de primer ingreso no válida. Vuelve a iniciar sesión.", "warning")
            return redirect(url_for("login"))

        if request.method == "POST":
            nueva = (request.form.get("nueva_contrasena") or "").strip()
            confirmar = (request.form.get("confirmar_contrasena") or "").strip()

            if not nueva or not confirmar:
                flash("Debes escribir y confirmar la contraseña.", "warning")
                return redirect(url_for("primer_ingreso"))

            if nueva != confirmar:
                flash("Las contraseñas no coinciden.", "danger")
                return redirect(url_for("primer_ingreso"))

            if len(nueva) < 4:
                flash("La contraseña debe tener al menos 4 caracteres.", "warning")
                return redirect(url_for("primer_ingreso"))

            conn = get_db_connection()
            cur = conn.cursor()

            try:
                hash_pass = generate_password_hash(nueva)
                cur.execute(
                    "UPDATE usuarios SET contrasena = ? WHERE id = ?",
                    (hash_pass, user_id),
                )
                conn.commit()
            except Exception as e:
                conn.rollback()
                conn.close()
                print(f"[WARN] Error al guardar contraseña en primer_ingreso: {e}")
                flash("Error al guardar la contraseña. Intenta de nuevo.", "danger")
                return redirect(url_for("primer_ingreso"))

            user = cur.execute(
                "SELECT * FROM usuarios WHERE id = ?",
                (user_id,),
            ).fetchone()
            conn.close()

            session.pop("primer_ingreso_id", None)
            session.pop("primer_ingreso_nombre", None)

            session["usuario"] = user["nombre"]
            rol_raw = user["rol"] or ""
            session["rol"] = (
                "admin"
                if rol_raw.lower().strip() in ("admin", "administrador")
                else "usuario"
            )

            flash("Contraseña creada correctamente.", "success")

            if session["rol"] == "admin":
                return redirect(url_for("admin.panel"))
            return redirect(url_for("usuario.panel"))

        return render_template("primer_ingreso.html", nombre=nombre)

    return app


def _abrir_url(url: str):
    try:
        webbrowser.open(url, new=1)
    except Exception:
        pass


if __name__ == "__main__":
    puerto = 5000

    # ✅ Candado anti-múltiples instancias SOLO EN .exe:
    # Si ya hay un servidor escuchando en 127.0.0.1:5000, no arrancamos otra vez.
    if getattr(sys, "frozen", False) and _port_ocupado("127.0.0.1", puerto):
        _abrir_url(f"http://127.0.0.1:{puerto}/admin/")
        raise SystemExit(0)

    app = create_app()

    ip = _ip_lan()

    print("\nHELP_APP en red local (SIN internet):")
    print(f"  PC:      http://127.0.0.1:{puerto}")
    print(f"  Tablet:  http://{ip}:{puerto}\n")

    # Abrir navegador del PC automáticamente
    #threading.Timer(1.0, lambda: _abrir_url(f"http://127.0.0.1:{puerto}")).start()

    # Servidor accesible por Wi-Fi
    app.run(host="0.0.0.0", port=puerto, debug=False, use_reloader=False)
