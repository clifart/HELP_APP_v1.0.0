from pathlib import Path
from datetime import datetime
import sqlite3
import textwrap

OUTFILE = Path("PRESENTACION_HELP_APP_EJECUTIVA.pdf")
DB_PATH = Path("database.db")

# Slide size (16:9)
W, H = 960, 540

# Brand palette
C_BG = (0.95, 0.98, 0.96)
C_DARK = (0.06, 0.42, 0.31)     # #0f6a4f approx
C_MID = (0.18, 0.49, 0.30)      # #2e7d32 approx
C_ACCENT = (0.37, 0.77, 0.46)   # #5ec576 approx
C_TEXT = (0.10, 0.16, 0.13)
C_WHITE = (1.0, 1.0, 1.0)
C_WARN = (0.95, 0.73, 0.13)
C_DANGER = (0.86, 0.23, 0.21)


def esc(s: str) -> str:
    return str(s).replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def rect(x, y, w, h, color, fill=True, stroke=False, lw=1):
    r, g, b = color
    ops = [f"{r:.4f} {g:.4f} {b:.4f} rg", f"{r:.4f} {g:.4f} {b:.4f} RG", f"{lw} w", f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re"]
    if fill and stroke:
        ops.append("B")
    elif fill:
        ops.append("f")
    elif stroke:
        ops.append("S")
    return ops


def txt(x, y, text, size=16, font="F1", color=C_TEXT):
    r, g, b = color
    return [
        "BT",
        f"/{font} {size} Tf",
        f"{r:.4f} {g:.4f} {b:.4f} rg",
        f"1 0 0 1 {x:.2f} {y:.2f} Tm",
        f"({esc(text)}) Tj",
        "ET",
    ]


def wrapped_lines(text, width_chars):
    return textwrap.wrap(text, width=width_chars) if text else [""]


def bullet_block(x, y, items, line_h=22, size=16, width_chars=72, bullet="- ", color=C_TEXT):
    ops = []
    cy = y
    for item in items:
        lines = wrapped_lines(item, width_chars)
        first = True
        for line in lines:
            prefix = bullet if first else "  "
            ops += txt(x, cy, prefix + line, size=size, font="F1", color=color)
            cy -= line_h
            first = False
        cy -= 4
    return ops


def kpi_from_db(path: Path):
    default = {
        "usuarios": "-",
        "tareas": "-",
        "historial_tareas": "-",
        "checklist_modulos": "-",
        "checklist_impresion": "-",
        "registro_excel_log": "-",
    }
    if not path.exists():
        return default
    try:
        conn = sqlite3.connect(str(path))
        cur = conn.cursor()
        for t in list(default.keys()):
            try:
                c = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                default[t] = str(c)
            except Exception:
                pass
        conn.close()
    except Exception:
        pass
    return default


def slide_shell(title, subtitle=None):
    ops = []
    # Background
    ops += rect(0, 0, W, H, C_BG)
    # Header band
    ops += rect(0, H - 82, W, 82, C_DARK)
    # Accent stripe
    ops += rect(0, H - 90, W, 8, C_ACCENT)
    # Footer bar
    ops += rect(0, 0, W, 26, C_MID)

    ops += txt(36, H - 52, title, size=28, font="F2", color=C_WHITE)
    if subtitle:
        ops += txt(36, H - 74, subtitle, size=12, font="F3", color=(0.90, 0.97, 0.93))
    return ops


def slide_cover(ts):
    ops = []
    ops += rect(0, 0, W, H, C_DARK)
    ops += rect(0, 0, W * 0.62, H, C_MID)
    ops += rect(0, H - 12, W, 12, C_ACCENT)
    ops += rect(0, 0, W, 22, C_ACCENT)

    ops += txt(56, 370, "HELP_APP", size=54, font="F2", color=C_WHITE)
    ops += txt(56, 332, "Presentacion ejecutiva", size=24, font="F3", color=(0.90, 0.97, 0.93))
    ops += txt(56, 294, "Enfoque, valor y proyeccion", size=24, font="F3", color=(0.90, 0.97, 0.93))

    ops += rect(540, 126, 360, 226, (1, 1, 1), fill=True, stroke=False)
    ops += txt(568, 316, "Resumen", size=26, font="F2", color=C_DARK)
    ops += bullet_block(
        568,
        286,
        [
            "Control de OP y tareas por proceso",
            "Reglas operativas y checklist obligatorio",
            "Autocierre por tiempo laboral",
            "Trazabilidad SQLite + Excel diario",
        ],
        line_h=24,
        size=14,
        width_chars=34,
        color=C_TEXT,
    )

    ops += txt(56, 80, f"Fecha de corte: {ts}", size=13, font="F1", color=C_WHITE)
    ops += txt(56, 58, "Producto interno de gestion operativa", size=12, font="F1", color=C_WHITE)
    return ops


def slide_agenda():
    ops = slide_shell("Agenda", "Que cubre esta presentacion")
    ops += rect(42, 66, 876, 364, C_WHITE)
    ops += bullet_block(
        72,
        390,
        [
            "Contexto operativo y problema objetivo",
            "Enfoque de la solucion y arquitectura actual",
            "Estado actual con metricas reales de uso",
            "Valor para operacion y administracion",
            "Riesgos tecnicos y acciones de mitigacion",
            "Hoja de ruta de evolucion a 90 dias",
        ],
        line_h=34,
        size=19,
        width_chars=64,
    )
    return ops


def slide_context():
    ops = slide_shell("Contexto y enfoque", "Problema a resolver")
    ops += rect(40, 66, 430, 364, C_WHITE)
    ops += txt(62, 394, "Problema operativo", size=22, font="F2", color=C_DARK)
    ops += bullet_block(
        62,
        360,
        [
            "Multiples procesos por OP y ejecucion paralela.",
            "Riesgo de tareas fuera de secuencia y cierres incompletos.",
            "Dificultad para auditar tiempos y cantidades en tiempo real.",
            "Dependencia de controles manuales no estandarizados.",
        ],
        line_h=24,
        size=14,
        width_chars=44,
    )

    ops += rect(490, 66, 430, 364, (0.91, 0.97, 0.93))
    ops += txt(512, 394, "Enfoque HELP_APP", size=22, font="F2", color=C_DARK)
    ops += bullet_block(
        512,
        360,
        [
            "Aplicacion web local (LAN) con bajo costo operativo.",
            "Reglas de negocio para secuencia y validacion de procesos.",
            "Checklist por modulo antes de cierre de tarea.",
            "Autocierre + horario extendido para continuidad de planta.",
            "Salida diaria a Excel para control administrativo.",
        ],
        line_h=22,
        size=14,
        width_chars=42,
    )
    return ops


def slide_architecture():
    ops = slide_shell("Arquitectura actual", "Estructura funcional del sistema")
    # Lanes
    ops += rect(46, 88, 200, 332, (0.89, 0.96, 0.91))
    ops += rect(262, 88, 300, 332, C_WHITE)
    ops += rect(578, 88, 336, 332, (0.95, 0.99, 0.96))

    ops += txt(62, 386, "Interfaz", size=18, font="F2", color=C_DARK)
    ops += bullet_block(62, 358, ["Templates Jinja", "JS para acciones", "Panel Admin/Usuario"], line_h=22, size=13, width_chars=20)

    ops += txt(278, 386, "Aplicacion Flask", size=18, font="F2", color=C_DARK)
    ops += bullet_block(
        278,
        358,
        [
            "app.py: boot + login + sesiones",
            "admin/views.py: gestion y modo tecnico",
            "usuario/views.py: flujo operativo diario",
            "core/auto_cierre.py: hilo de autocierre",
        ],
        line_h=21,
        size=13,
        width_chars=34,
    )

    ops += txt(594, 386, "Persistencia y salida", size=18, font="F2", color=C_DARK)
    ops += bullet_block(
        594,
        358,
        [
            "SQLite (database.db)",
            "historial_tareas + checklist_modulos",
            "registro_excel_log (anti duplicados)",
            "carpeta diaria con tareas.xlsx/csv",
        ],
        line_h=21,
        size=13,
        width_chars=36,
    )
    return ops


def slide_flow():
    ops = slide_shell("Flujo operativo", "Desde OP maestra hasta cierre trazable")
    ops += rect(40, 82, 880, 348, C_WHITE)

    steps = [
        "1. Admin crea OP maestra activa",
        "2. Usuario selecciona OP y proceso",
        "3. Sistema valida reglas de secuencia",
        "4. Usuario ejecuta tarea (inicio/pausa/reanudar)",
        "5. Checklist por modulo antes de cierre",
        "6. Finalizacion y registro en historial + Excel",
    ]

    y = 388
    for i, s in enumerate(steps):
        box_color = (0.90, 0.97, 0.93) if i % 2 == 0 else (0.95, 0.99, 0.96)
        ops += rect(64, y - 30, 832, 40, box_color)
        ops += txt(84, y - 14, s, size=15, font="F2", color=C_DARK)
        y -= 52

    return ops


def slide_metrics(kpi, ts):
    ops = slide_shell("Estado actual", "Metricas reales de base de datos")
    ops += txt(40, 446, f"Corte de datos: {ts}", size=12, font="F3", color=C_WHITE)

    cards = [
        ("Usuarios", kpi["usuarios"]),
        ("Tareas", kpi["tareas"]),
        ("Historial tareas", kpi["historial_tareas"]),
        ("Checklist modulos", kpi["checklist_modulos"]),
        ("Checklist impresion", kpi["checklist_impresion"]),
        ("Tokens Excel", kpi["registro_excel_log"]),
    ]

    x0, y0 = 56, 302
    w, h = 268, 108
    gapx, gapy = 26, 30

    idx = 0
    for r in range(2):
        for c in range(3):
            label, val = cards[idx]
            x = x0 + c * (w + gapx)
            y = y0 - r * (h + gapy)
            ops += rect(x, y, w, h, C_WHITE)
            ops += rect(x, y + h - 8, w, 8, C_ACCENT)
            ops += txt(x + 16, y + 68, label, size=16, font="F2", color=C_DARK)
            ops += txt(x + 16, y + 34, str(val), size=30, font="F2", color=C_TEXT)
            idx += 1

    ops += txt(56, 52, "La base ya refleja uso productivo y trazabilidad continua.", size=14, font="F1", color=C_DARK)
    return ops


def slide_value():
    ops = slide_shell("Valor de negocio", "Impacto operativo esperado")
    ops += rect(42, 66, 876, 364, C_WHITE)

    ops += rect(66, 310, 400, 96, (0.89, 0.96, 0.91))
    ops += txt(84, 372, "Operacion", size=20, font="F2", color=C_DARK)
    ops += bullet_block(84, 346, ["Menos reproceso por flujo controlado", "Cierre de tareas mas consistente"], line_h=20, size=13, width_chars=36)

    ops += rect(494, 310, 400, 96, (0.95, 0.99, 0.96))
    ops += txt(512, 372, "Calidad y trazabilidad", size=20, font="F2", color=C_DARK)
    ops += bullet_block(512, 346, ["Checklist obligatorio por modulo", "Historial tecnico auditable"], line_h=20, size=13, width_chars=36)

    ops += rect(66, 184, 400, 96, (0.95, 0.99, 0.96))
    ops += txt(84, 246, "Gestion", size=20, font="F2", color=C_DARK)
    ops += bullet_block(84, 220, ["Visibilidad por OP/proceso/usuario", "Datos listos para KPI"], line_h=20, size=13, width_chars=36)

    ops += rect(494, 184, 400, 96, (0.89, 0.96, 0.91))
    ops += txt(512, 246, "Soporte", size=20, font="F2", color=C_DARK)
    ops += bullet_block(512, 220, ["Modo tecnico para mantenimiento", "Prueba controlada de autocierre"], line_h=20, size=13, width_chars=36)

    return ops


def slide_risks():
    ops = slide_shell("Riesgos y deuda tecnica", "Puntos de atencion prioritaria")
    ops += rect(40, 66, 430, 364, (1.0, 0.98, 0.93))
    ops += rect(490, 66, 430, 364, C_WHITE)

    ops += txt(62, 394, "Riesgos actuales", size=22, font="F2", color=C_DANGER)
    ops += bullet_block(
        62,
        360,
        [
            "Secretos hardcodeados en codigo fuente.",
            "Alta concentracion de logica en vistas.",
            "Esquema con legado (columnas coexistentes).",
            "Import inconsistente de record mensual.",
        ],
        line_h=24,
        size=14,
        width_chars=43,
        color=C_TEXT,
    )

    ops += txt(512, 394, "Mitigacion propuesta", size=22, font="F2", color=C_DARK)
    ops += bullet_block(
        512,
        360,
        [
            "Mover secretos a entorno seguro.",
            "Separar servicios de negocio por dominio.",
            "Estandarizar migraciones y limpiar legado.",
            "Completar pruebas unitarias e integracion.",
            "Agregar auditoria minima de eventos criticos.",
        ],
        line_h=22,
        size=14,
        width_chars=42,
        color=C_TEXT,
    )
    return ops


def slide_roadmap():
    ops = slide_shell("Hoja de ruta 90 dias", "Evolucion incremental sin reescritura")
    ops += rect(42, 66, 876, 364, C_WHITE)

    phases = [
        ("0-30 dias", "Estabilizacion", ["Seguridad de secretos", "Correccion import record mensual", "Backups automatizados"]),
        ("31-60 dias", "Calidad tecnica", ["Extraer servicios de negocio", "Pruebas unitarias/autocierre", "Auditoria de eventos"]),
        ("61-90 dias", "Escalamiento", ["API de KPIs", "Dashboard de productividad", "Preparar migracion a PostgreSQL"]),
    ]

    x = 66
    w = 264
    for days, title, bullets in phases:
        ops += rect(x, 126, w, 256, (0.95, 0.99, 0.96))
        ops += rect(x, 340, w, 42, C_DARK)
        ops += txt(x + 14, 355, days, size=15, font="F2", color=C_WHITE)
        ops += txt(x + 14, 320, title, size=18, font="F2", color=C_DARK)
        ops += bullet_block(x + 14, 294, bullets, line_h=20, size=12, width_chars=30)
        x += 288

    return ops


def slide_close(ts):
    ops = []
    ops += rect(0, 0, W, H, C_DARK)
    ops += rect(0, H - 12, W, 12, C_ACCENT)
    ops += rect(0, 0, W, 20, C_ACCENT)

    ops += txt(70, 374, "HELP_APP", size=52, font="F2", color=C_WHITE)
    ops += txt(70, 334, "Listo para la siguiente etapa de madurez", size=24, font="F3", color=(0.90, 0.97, 0.93))

    ops += rect(70, 158, 820, 132, (1, 1, 1))
    ops += bullet_block(
        96,
        258,
        [
            "Ya cubre el ciclo operativo critico de produccion.",
            "Prioridad inmediata: seguridad y calidad tecnica.",
            "Siguiente salto: KPI en tiempo casi real para decision operativa.",
        ],
        line_h=28,
        size=17,
        width_chars=66,
        color=C_TEXT,
    )

    ops += txt(70, 74, f"Generado automaticamente: {ts}", size=12, font="F1", color=C_WHITE)
    return ops


def stream_for_slide(ops, i, n):
    # Add footer page marker on non-cover slides in shell and custom on all slides
    extra = []
    extra += txt(W - 108, 6, f"{i}/{n}", size=10, font="F1", color=C_WHITE if i in (1, n) else (0.92, 0.98, 0.94))
    data = "\n".join(ops + extra).encode("latin-1", errors="replace")
    return data


def build_pdf(slides_ops):
    objects = []

    def add_obj(b):
        objects.append(b)
        return len(objects)

    # fonts
    f1 = add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    f2 = add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    f3 = add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique >>")

    pages_id = add_obj(b"<< >>")

    page_ids = []
    total = len(slides_ops)

    for idx, ops in enumerate(slides_ops, start=1):
        stream = stream_for_slide(ops, idx, total)
        cobj = b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream"
        c_id = add_obj(cobj)

        page = (
            b"<< /Type /Page /Parent " + str(pages_id).encode("ascii") + b" 0 R "
            + b"/MediaBox [0 0 " + str(W).encode("ascii") + b" " + str(H).encode("ascii") + b"] "
            + b"/Resources << /Font << /F1 " + str(f1).encode("ascii") + b" 0 R /F2 " + str(f2).encode("ascii") + b" 0 R /F3 " + str(f3).encode("ascii") + b" 0 R >> >> "
            + b"/Contents " + str(c_id).encode("ascii") + b" 0 R >>"
        )
        p_id = add_obj(page)
        page_ids.append(p_id)

    kids = b"[ " + b" ".join((str(p).encode("ascii") + b" 0 R") for p in page_ids) + b" ]"
    pages = b"<< /Type /Pages /Kids " + kids + b" /Count " + str(len(page_ids)).encode("ascii") + b" >>"
    objects[pages_id - 1] = pages

    catalog = add_obj(b"<< /Type /Catalog /Pages " + str(pages_id).encode("ascii") + b" 0 R >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]

    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{i} 0 obj\n".encode("ascii"))
        out.extend(obj)
        out.extend(b"\nendobj\n")

    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objects)+1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))

    out.extend(
        b"trailer\n<< /Size " + str(len(objects)+1).encode("ascii") + b" /Root " + str(catalog).encode("ascii") + b" 0 R >>\n"
    )
    out.extend(b"startxref\n")
    out.extend(str(xref_pos).encode("ascii") + b"\n%%EOF\n")

    OUTFILE.write_bytes(bytes(out))


def main():
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    kpi = kpi_from_db(DB_PATH)

    slides = [
        slide_cover(ts),
        slide_agenda(),
        slide_context(),
        slide_architecture(),
        slide_flow(),
        slide_metrics(kpi, ts),
        slide_value(),
        slide_risks(),
        slide_roadmap(),
        slide_close(ts),
    ]

    build_pdf(slides)
    print(f"OK: {OUTFILE}")


if __name__ == "__main__":
    main()
