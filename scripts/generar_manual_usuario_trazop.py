from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
CAPTURES = ROOT / "manual_capturas_trazop" / "capturas_trazop"
OUTPUT = ROOT / "MANUAL_USUARIO_TRAZOP_v1.2.10.pdf"
LOGO = ROOT / "static" / "img" / "helpapp2.png"

GREEN = colors.HexColor("#0F6A4F")
GREEN_2 = colors.HexColor("#2E8B57")
LIGHT_GREEN = colors.HexColor("#E8F4EF")
TEXT = colors.HexColor("#27332F")
MUTED = colors.HexColor("#66736E")
WHITE = colors.white


def register_fonts():
    regular = Path("C:/Windows/Fonts/arial.ttf")
    bold = Path("C:/Windows/Fonts/arialbd.ttf")
    if regular.exists() and bold.exists():
        pdfmetrics.registerFont(TTFont("TrazOp", str(regular)))
        pdfmetrics.registerFont(TTFont("TrazOp-Bold", str(bold)))
        return "TrazOp", "TrazOp-Bold"
    return "Helvetica", "Helvetica-Bold"


FONT, FONT_BOLD = register_fonts()


styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name="ManualTitle",
    fontName=FONT_BOLD,
    fontSize=27,
    leading=32,
    textColor=GREEN,
    alignment=TA_CENTER,
    spaceAfter=10,
))
styles.add(ParagraphStyle(
    name="ManualSubtitle",
    fontName=FONT,
    fontSize=14,
    leading=20,
    textColor=MUTED,
    alignment=TA_CENTER,
    spaceAfter=12,
))
styles.add(ParagraphStyle(
    name="SectionTitle",
    fontName=FONT_BOLD,
    fontSize=19,
    leading=23,
    textColor=GREEN,
    spaceAfter=10,
))
styles.add(ParagraphStyle(
    name="BodyManual",
    fontName=FONT,
    fontSize=10.5,
    leading=15,
    textColor=TEXT,
    alignment=TA_LEFT,
    spaceAfter=7,
))
styles.add(ParagraphStyle(
    name="BulletManual",
    parent=styles["BodyManual"],
    leftIndent=15,
    firstLineIndent=-8,
    bulletIndent=5,
    spaceAfter=4,
))
styles.add(ParagraphStyle(
    name="CaptionManual",
    fontName=FONT,
    fontSize=8.5,
    leading=11,
    textColor=MUTED,
    alignment=TA_CENTER,
    spaceBefore=5,
    spaceAfter=5,
))
styles.add(ParagraphStyle(
    name="Callout",
    fontName=FONT_BOLD,
    fontSize=10,
    leading=14,
    textColor=GREEN,
    alignment=TA_CENTER,
))


def paragraph(text):
    return Paragraph(text, styles["BodyManual"])


def bullets(items):
    return [Paragraph(f"• {item}", styles["BulletManual"]) for item in items]


def screenshot(path: Path, max_width=17.1 * cm, max_height=12.5 * cm):
    width, height = ImageReader(str(path)).getSize()
    scale = min(max_width / width, max_height / height)
    image = Image(str(path), width=width * scale, height=height * scale)
    frame = Table([[image]], colWidths=[image.drawWidth + 0.22 * cm])
    frame.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, GREEN_2),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7FBF9")),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    return frame


def add_figure(story, number, filename, caption, max_height=12.5 * cm):
    path = CAPTURES / filename
    if not path.exists():
        raise FileNotFoundError(path)
    story.append(Spacer(1, 0.12 * cm))
    story.append(screenshot(path, max_height=max_height))
    story.append(Paragraph(f"Figura {number}. {caption}", styles["CaptionManual"]))


def header_footer(canvas, doc):
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(GREEN)
    canvas.setLineWidth(1)
    canvas.line(1.7 * cm, height - 1.35 * cm, width - 1.7 * cm, height - 1.35 * cm)
    canvas.setFont(FONT_BOLD, 8.5)
    canvas.setFillColor(GREEN)
    canvas.drawString(1.7 * cm, height - 1.05 * cm, "TrazOp | Manual del usuario final")
    canvas.setFont(FONT, 8)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(width - 1.7 * cm, 0.85 * cm, f"Página {doc.page}")
    canvas.restoreState()


def cover(canvas, doc):
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(GREEN)
    canvas.rect(0, height - 1.0 * cm, width, 1.0 * cm, fill=1, stroke=0)
    canvas.setFillColor(GREEN_2)
    canvas.rect(0, 0, width, 0.65 * cm, fill=1, stroke=0)
    canvas.restoreState()


def build_story():
    story = []

    story.append(Spacer(1, 1.5 * cm))
    if LOGO.exists():
        logo = Image(str(LOGO), width=7.3 * cm, height=3.65 * cm)
        story.append(Table([[logo]], colWidths=[17 * cm], style=[("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    story.append(Spacer(1, 0.7 * cm))
    story.append(Paragraph("MANUAL DEL USUARIO FINAL", styles["ManualTitle"]))
    story.append(Paragraph("Registro, control y trazabilidad de actividades productivas", styles["ManualSubtitle"]))
    story.append(Spacer(1, 0.6 * cm))
    cover_box = Table([[Paragraph(
        "Guía práctica para iniciar tareas, gestionar pausas, completar checklists, "
        "registrar cantidades y consultar el historial.", styles["Callout"]
    )]], colWidths=[14.5 * cm])
    cover_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GREEN),
        ("BOX", (0, 0), (-1, -1), 1, GREEN),
        ("LEFTPADDING", (0, 0), (-1, -1), 18),
        ("RIGHTPADDING", (0, 0), (-1, -1), 18),
        ("TOPPADDING", (0, 0), (-1, -1), 16),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
    ]))
    story.append(Table([[cover_box]], colWidths=[17 * cm], style=[("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    story.append(Spacer(1, 2.4 * cm))
    story.append(Paragraph("Versión del manual: 1.0", styles["ManualSubtitle"]))
    story.append(Paragraph("Aplicación TrazOp v1.2.10", styles["ManualSubtitle"]))
    story.append(PageBreak())

    story.append(Paragraph("Introducción", styles["SectionTitle"]))
    story.append(paragraph(
        "TrazOp facilita el registro, seguimiento y control de las actividades realizadas "
        "durante el proceso productivo. Cada operario puede administrar sus tareas desde "
        "un computador o dispositivo móvil, dejando evidencia de tiempos, cantidades y controles."
    ))
    story.append(paragraph(
        "La aplicación acompaña al usuario desde el inicio de una actividad hasta su cierre. "
        "Antes de finalizar, presenta el checklist específico del proceso para verificar los "
        "controles de calidad, producción, limpieza o mantenimiento aplicables."
    ))
    story.append(Spacer(1, 0.35 * cm))
    story.append(Paragraph("¿Cómo ayuda al usuario final?", styles["SectionTitle"]))
    story.extend(bullets([
        "Presenta claramente las órdenes y tareas asignadas.",
        "Registra las horas de inicio, pausa, reanudación y finalización.",
        "Descuenta las pausas del tiempo efectivo de trabajo.",
        "Utiliza un checklist específico para cada proceso.",
        "Evita finalizar actividades que no cumplan sus controles.",
        "Calcula automáticamente valores como la cantidad de etiquetas en Flexo.",
        "Conserva un historial organizado para consulta y trazabilidad.",
    ]))
    story.append(Spacer(1, 0.4 * cm))
    flow = Table([
        ["1", "Ingresar"], ["2", "Seleccionar OP y proceso"], ["3", "Iniciar la tarea"],
        ["4", "Completar el checklist"], ["5", "Finalizar"], ["6", "Consultar historial"],
    ], colWidths=[1.2 * cm, 12.8 * cm])
    flow.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (-1, -1), TEXT),
        ("BACKGROUND", (0, 0), (0, -1), GREEN),
        ("TEXTCOLOR", (0, 0), (0, -1), WHITE),
        ("FONTNAME", (0, 0), (0, -1), FONT_BOLD),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B8D8CA")),
        ("ROWBACKGROUNDS", (1, 0), (-1, -1), [colors.white, LIGHT_GREEN]),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(flow)

    sections = [
        ("1. Inicio de sesión", "0.png",
         ["Seleccione su usuario en la lista.", "Escriba la contraseña asignada.", "Pulse <b>Entrar</b>."],
         "Pantalla de inicio de sesión de TrazOp.",
         "Cada operario debe utilizar su propia cuenta para que tareas, tiempos, cantidades y checklists queden registrados correctamente a su nombre."),
        ("2. Panel principal", "01.png",
         ["Seleccione una orden de producción.", "Revise la descripción asociada.", "Elija el proceso que va a realizar.", "Consulte las tareas activas en la tabla."],
         "Panel principal del usuario y registro de tareas.",
         "El panel reúne las actividades del día y permite acceder a las acciones disponibles para cada tarea."),
        ("3. Selección de orden y proceso", "02.png",
         ["Seleccione la OP.", "Confirme la descripción.", "Seleccione la tarea o proceso.", "Pulse <b>ACEPTAR</b> para iniciar."],
         "Selección de la orden de producción y del proceso.",
         "Verifique siempre la OP y el proceso antes de iniciar; de esta selección depende que la trazabilidad quede asociada al trabajo correcto."),
        ("4. Tarea iniciada", "03.png",
         ["La hora de inicio se registra automáticamente.", "FIN AUT muestra la hora estimada de cierre según el turno.", "Las acciones disponibles aparecen a la derecha."],
         "Tarea iniciada y controles disponibles.",
         "Los procesos exentos muestran N/A en cantidad y Sin checklist. Los demás requieren completar sus controles antes de finalizar."),
        ("5. Pausar una tarea", "04.png",
         ["Pulse <b>Pausa</b> cuando interrumpa temporalmente la actividad.", "El tiempo pausado no se suma al tiempo efectivo.", "Mientras está pausada, la tarea no puede finalizarse."],
         "Tarea pausada y opción para reanudar.",
         "La pausa permite conservar una medición real del tiempo trabajado."),
        ("6. Reanudar una tarea", "05.png",
         ["Pulse <b>Reanudar</b> cuando continúe el trabajo.", "TrazOp reactiva los controles de la tarea.", "El cronómetro continúa descontando el periodo pausado."],
         "Confirmación de tarea reanudada.",
         "Después de reanudar, vuelven a estar disponibles las acciones normales de la tarea."),
        ("7. Tarea con checklist obligatorio", "07.png",
         ["Pulse el botón azul <b>Checklist</b>.", "Finalizar permanece condicionado al cumplimiento del formulario.", "En Flexo, la cantidad inicia en cero y será calculada automáticamente."],
         "Tarea de Impresión FLEXO con checklist obligatorio.",
         "Cada proceso abre su checklist específico; Flexo ya no utiliza el checklist general de impresión."),
        ("8. Checklist de Impresión FLEXO", "08.png",
         ["Marque Sí, No o N/A en cada control.", "Ingrese los datos de los rollos.", "Revise responsable y fecha.", "Agregue observaciones cuando sea necesario."],
         "Checklist de control para el proceso de Impresión FLEXO.",
         "Los puntos 4.1 y 4.2 son necesarios para calcular la cantidad producida."),
        ("9. Cálculos automáticos de Flexo", "09.png",
         ["4.5 calcula el peso del rollo terminado.", "4.6 calcula la cantidad de etiquetas.", "4.7 informa la cantidad de rollos generados."],
         "Datos ingresados y cálculos automáticos del checklist Flexo.",
         "En el ejemplo: 120 metros × 18 etiquetas por metro = <b>2.160 etiquetas</b>."),
        ("10. Cantidad transferida al panel", "10.png",
         ["Al guardar el checklist, la cantidad de 4.6 pasa a la tarea.", "El campo queda bloqueado para evitar cambios accidentales.", "Finalizar queda disponible."],
         "Cantidad transferida automáticamente desde el checklist Flexo.",
         "El usuario no debe copiar ni volver a escribir la cantidad calculada."),
        ("11. Finalización de la tarea", "11.png",
         ["Pulse <b>Finalizar</b>.", "TrazOp confirma el proceso, el tiempo total y las horas extras.", "La tarea desaparece del panel y pasa al historial."],
         "Confirmación de finalización de una tarea.",
         "Al finalizar quedan guardados el usuario, la OP, el proceso, la cantidad, los tiempos y el checklist."),
        ("12. Menú de navegación", "12.png",
         ["Historial: consulta actividades finalizadas.", "Calc. de Corte: abre la herramienta de aprovechamiento del material.", "Pulse X para cerrar el menú."],
         "Menú de navegación y herramientas del usuario.",
         "El menú verde está ubicado en la esquina superior derecha del panel."),
        ("13. Historial de tareas finalizadas", "13.png",
         ["Consulte OP, descripción y cantidad.", "Revise horas de inicio y finalización.", "Verifique tiempo de tarea, horas extras, pausas y tipo de cierre."],
         "Historial de actividades y cantidades producidas.",
         "El historial proporciona trazabilidad de las actividades realizadas por el operario."),
        ("14. Calculadora de corte", "14.png",
         ["Seleccione el tamaño del pliego.", "Ingrese ancho y alto de la pieza.", "Indique la cantidad requerida."],
         "Configuración inicial de la calculadora de corte.",
         "La herramienta compara orientaciones y estima el material requerido."),
        ("15. Resultado del cálculo de corte", "15.png",
         ["Revise el número de pliegos necesarios.", "Compare las opciones de orientación.", "Consulte piezas por pliego, sobrantes y corte escalonado.", "Use la visualización para validar la distribución."],
         "Resultado, comparación y visualización del corte.",
         "TrazOp destaca la alternativa recomendada para mejorar el aprovechamiento y reducir desperdicios."),
    ]

    for number, (title, filename, items, caption, note) in enumerate(sections, start=1):
        story.append(PageBreak())
        story.append(Paragraph(title, styles["SectionTitle"]))
        story.append(paragraph(note))
        story.extend(bullets(items))
        max_h = 13.0 * cm
        if filename in {"08.png", "09.png", "15.png"}:
            max_h = 14.3 * cm
        add_figure(story, number, filename, caption, max_height=max_h)

    story.append(PageBreak())
    story.append(Paragraph("Recomendaciones de uso", styles["SectionTitle"]))
    story.extend(bullets([
        "Utilice siempre su usuario personal; no comparta credenciales.",
        "Confirme la OP y el proceso antes de iniciar una tarea.",
        "Use Pausa cuando la actividad se interrumpa y Reanudar al continuar.",
        "Diligencie cada checklist con información real y completa.",
        "No cierre ni actualice la página mientras se está guardando información.",
        "Revise los mensajes de confirmación antes de continuar.",
        "Cierre sesión al terminar el turno o cuando deje el dispositivo sin supervisión.",
    ]))
    story.append(Spacer(1, 0.6 * cm))
    closing = Table([[Paragraph(
        "TrazOp simplifica el registro operativo, reduce la duplicación de datos y "
        "conserva la trazabilidad de cada actividad productiva.", styles["Callout"]
    )]], colWidths=[15.2 * cm])
    closing.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GREEN),
        ("BOX", (0, 0), (-1, -1), 1, GREEN),
        ("LEFTPADDING", (0, 0), (-1, -1), 16),
        ("RIGHTPADDING", (0, 0), (-1, -1), 16),
        ("TOPPADDING", (0, 0), (-1, -1), 18),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
    ]))
    story.append(closing)
    return story


def main():
    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        rightMargin=1.7 * cm,
        leftMargin=1.7 * cm,
        topMargin=1.65 * cm,
        bottomMargin=1.45 * cm,
        title="Manual del usuario final - TrazOp",
        author="HELP APP",
        subject="Guía de manejo de TrazOp",
    )
    doc.build(build_story(), onFirstPage=cover, onLaterPages=header_footer)
    print(f"PDF generado: {OUTPUT}")


if __name__ == "__main__":
    main()
