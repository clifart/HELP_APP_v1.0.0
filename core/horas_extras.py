from datetime import datetime


def _parse_iso(raw):
    try:
        return datetime.fromisoformat(str(raw or "").replace("Z", "").strip())
    except Exception:
        return None


def segundos_a_hms(total_seg):
    try:
        seg = max(0, int(total_seg or 0))
    except Exception:
        seg = 0
    horas = seg // 3600
    minutos = (seg % 3600) // 60
    segundos = seg % 60
    return f"{horas:02d}:{minutos:02d}:{segundos:02d}"


def calcular_tiempo_total_y_horas_extras(
    inicio,
    fin,
    pausa_acum_seg=0,
    horario_extendido=0,
    extendido_desde=None,
):
    """
    Devuelve (tiempo_total_hms, horas_extras_hms) en formato HH:MM:SS.

    - tiempo_total: duracion neta (fin - inicio - pausas).
    - horas_extras: tramo neto desde extendido_desde hasta fin, solo si horario_extendido=1.
    """
    dt_inicio = _parse_iso(inicio)
    dt_fin = _parse_iso(fin)
    if not dt_inicio or not dt_fin:
        return "", "00:00:00"

    bruto_total = max(0, int((dt_fin - dt_inicio).total_seconds()))
    pausa_total = max(0, int(pausa_acum_seg or 0))
    neto_total = max(0, bruto_total - pausa_total)

    extras_seg = 0
    if int(horario_extendido or 0) == 1:
        dt_ext = _parse_iso(extendido_desde)
        if dt_ext:
            if dt_ext < dt_inicio:
                dt_ext = dt_inicio
            if dt_ext < dt_fin:
                bruto_extras = max(0, int((dt_fin - dt_ext).total_seconds()))
                # Reparto proporcional de pausas: no hay trazabilidad por tramo.
                pausa_extras = 0
                if bruto_total > 0 and pausa_total > 0:
                    pausa_extras = int(round(pausa_total * (bruto_extras / float(bruto_total))))
                extras_seg = max(0, bruto_extras - pausa_extras)
                extras_seg = min(extras_seg, neto_total)

    return segundos_a_hms(neto_total), segundos_a_hms(extras_seg)
