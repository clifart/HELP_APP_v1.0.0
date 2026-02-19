from pathlib import Path
from datetime import datetime
import textwrap

TITLE = "HELP_APP - Presentacion tecnica"
OUTFILE = Path("PRESENTACION_HELP_APP_ENFOQUE_PROYECCION.pdf")

sections = [
    ("PORTADA", [
        "HELP_APP", 
        "Presentacion: enfoque y proyeccion", 
        "Fecha: 2026-02-18",
        "", 
        "Sistema interno para control de OP, tareas y trazabilidad operativa.",
    ]),
    ("1) CONTEXTO Y PROBLEMA", [
        "Planta con multiples procesos por OP y necesidad de control en tiempo real.",
        "Riesgos operativos sin sistema: desorden en secuencia, perdida de trazabilidad,",
        "cierres tardios y dificultad para medir productividad por usuario/proceso.",
        "", 
        "HELP_APP responde con una plataforma web local para administrar OP,",
        "ejecutar tareas por proceso y consolidar historial tecnico-operativo.",
    ]),
    ("2) ENFOQUE DE LA SOLUCION", [
        "Principio 1: Simplicidad operativa (Flask + SQLite, despliegue LAN).",
        "Principio 2: Control de flujo por reglas de negocio (dependencia de impresion).",
        "Principio 3: Trazabilidad completa (tarea activa -> historial -> Excel diario).",
        "Principio 4: Continuidad de operacion (autocierre y horario extendido).",
        "Principio 5: Soporte tecnico integrado (modo tecnico y pruebas de autocierre).",
    ]),
    ("3) ARQUITECTURA ACTUAL", [
        "Entrada: app.py (boot, login, sesiones, blueprints, hilo autocierre).",
        "Admin: admin/views.py (usuarios, OP, historial, modo tecnico, exportaciones).",
        "Usuario: usuario/views.py (inicio tarea, checklist, pausa/reanudar, cierre).",
        "Core: db.py, horarios.py, auto_cierre.py, registro_diario.py, exportar_excel.py.",
        "UI: templates Jinja + JS para acciones asincronas criticas.",
    ]),
    ("4) ESTADO ACTUAL (BD REAL)", [
        "Corte: 2026-02-18", 
        "usuarios: 26", 
        "tareas: 643", 
        "historial_tareas: 564", 
        "checklist_modulos: 470", 
        "checklist_impresion: 248", 
        "registro_excel_log: 417", 
        "historial_mensual: 1",
        "", 
        "La operacion ya tiene volumen suficiente para fase de KPIs y analitica.",
    ]),
    ("5) VALOR OPERATIVO", [
        "Visibilidad diaria de ejecucion por usuario y proceso.",
        "Menor riesgo de cierres incompletos por validaciones + checklist obligatorio.",
        "Autocierre de tareas olvidadas segun ventanas laborales.",
        "Exportacion y carpeta diaria para control administrativo y auditoria.",
        "Base objetiva para medir tiempos, cantidades y cumplimiento de flujo.",
    ]),
    ("6) RIESGOS A RESOLVER", [
        "Secretos en codigo (secret_key, clave tecnica).",
        "Alta concentracion de logica en archivos de vistas.",
        "Esquema con columnas heredadas y migracion no centralizada.",
        "Inconsistencia puntual en import de record mensual.",
        "Cobertura de pruebas automatizadas todavia limitada.",
    ]),
    ("7) PROYECCION (90 DIAS)", [
        "0-30 dias: endurecer seguridad y estabilizar migraciones.",
        "31-60 dias: modularizar reglas y ampliar pruebas unitarias/integracion.",
        "61-90 dias: exponer KPIs por API y tablero de productividad.",
        "", 
        "Resultado esperado: evolucion de herramienta local a plataforma",
        "de control productivo con indicadores en tiempo casi real.",
    ]),
    ("8) CIERRE", [
        "HELP_APP ya resuelve el ciclo critico operativo.",
        "La estrategia recomendada es evolucion incremental, no reescritura.",
        "", 
        "Prioridad: seguridad + calidad tecnica + observabilidad.",
        "Con esa ruta, el sistema puede escalar funcionalmente",
        "sin perder continuidad de operacion.",
    ]),
]

PAGE_W = 612
PAGE_H = 792
MARGIN_L = 50
MARGIN_T = 760
LINE_H = 15
MAX_COLS = 85
MAX_LINES = 44


def esc_pdf(text: str) -> str:
    return text.replace('\\', r'\\').replace('(', r'\(').replace(')', r'\)')


def build_lines():
    out = []
    for title, items in sections:
        out.append(title)
        out.append("-" * min(len(title), 70))
        for raw in items:
            if not raw:
                out.append("")
                continue
            wrapped = textwrap.wrap(raw, width=MAX_COLS)
            out.extend(wrapped if wrapped else [""])
        out.append("")
    return out


def paginate(lines):
    pages = []
    for i in range(0, len(lines), MAX_LINES):
        pages.append(lines[i:i + MAX_LINES])
    return pages


def page_stream(lines, page_no, total_pages):
    cmds = []
    cmds.append("BT")
    cmds.append("/F1 11 Tf")
    cmds.append(f"{MARGIN_L} {MARGIN_T} Td")
    cmds.append(f"{LINE_H} TL")

    for i, line in enumerate(lines):
        prefix = "" if i > 0 else ""
        txt = esc_pdf(prefix + line)
        if i == 0:
            cmds.append(f"({txt}) Tj")
        else:
            cmds.append("T*")
            cmds.append(f"({txt}) Tj")

    # footer
    cmds.append("T*")
    cmds.append("T*")
    footer = esc_pdf(f"Pagina {page_no}/{total_pages}  |  Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    cmds.append(f"({footer}) Tj")

    cmds.append("ET")
    return "\n".join(cmds).encode("latin-1", errors="replace")


def build_pdf(path: Path):
    lines = build_lines()
    pages = paginate(lines)

    objects = []

    def add_obj(data: bytes):
        objects.append(data)
        return len(objects)

    # 1) font
    font_id = add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    # 2) placeholder pages root
    pages_id = add_obj(b"<< >>")

    page_ids = []
    for idx, p_lines in enumerate(pages, start=1):
        stream = page_stream(p_lines, idx, len(pages))
        content = b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream"
        content_id = add_obj(content)

        page_dict = (
            b"<< /Type /Page /Parent " + str(pages_id).encode("ascii") + b" 0 R "
            b"/MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 " + str(font_id).encode("ascii") + b" 0 R >> >> "
            b"/Contents " + str(content_id).encode("ascii") + b" 0 R >>"
        )
        page_id = add_obj(page_dict)
        page_ids.append(page_id)

    kids = b"[ " + b" ".join((str(pid).encode("ascii") + b" 0 R") for pid in page_ids) + b" ]"
    pages_dict = b"<< /Type /Pages /Kids " + kids + b" /Count " + str(len(page_ids)).encode("ascii") + b" >>"
    objects[pages_id - 1] = pages_dict

    catalog_id = add_obj(b"<< /Type /Catalog /Pages " + str(pages_id).encode("ascii") + b" 0 R >>")

    # Write file
    out = bytearray()
    out.extend(b"%PDF-1.4\n")
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

    trailer = (
        b"trailer\n<< /Size " + str(len(objects)+1).encode("ascii") +
        b" /Root " + str(catalog_id).encode("ascii") + b" 0 R >>\n"
    )
    out.extend(trailer)
    out.extend(b"startxref\n")
    out.extend(str(xref_pos).encode("ascii") + b"\n%%EOF\n")

    path.write_bytes(bytes(out))


if __name__ == "__main__":
    build_pdf(OUTFILE)
    print(f"OK: {OUTFILE}")
