from datetime import datetime, time, timedelta


def _min(h, m):
    return int(h) * 60 + int(m)


_DIURNO = {
    0: [(_min(6, 0), _min(14, 0)), (_min(14, 0), _min(22, 0))],   # Lunes
    1: [(_min(6, 0), _min(14, 0)), (_min(14, 0), _min(22, 0))],   # Martes
    2: [(_min(6, 0), _min(14, 0)), (_min(14, 0), _min(22, 0))],   # Miércoles
    3: [(_min(6, 0), _min(14, 0)), (_min(14, 0), _min(22, 0))],   # Jueves
    4: [(_min(6, 0), _min(14, 0)), (_min(14, 0), _min(22, 0))],   # Viernes
    5: [(_min(6, 0), _min(12, 0))],   # Sábado (6-10 y 8-12 -> 6-12)
    6: [],                            # Domingo (descanso)
}

_NOCTURNO = {
    0: [(_min(20, 30), _min(24, 0))],                         # Lunes (20:30-24:00)
    1: [(_min(0, 0), _min(6, 0)), (_min(20, 30), _min(24, 0))],  # Martes
    2: [(_min(0, 0), _min(6, 0)), (_min(20, 30), _min(24, 0))],  # Miércoles
    3: [(_min(0, 0), _min(6, 0)), (_min(20, 30), _min(24, 0))],  # Jueves
    4: [(_min(0, 0), _min(6, 0)), (_min(21, 30), _min(24, 0))],  # Viernes (21:30-24:00)
    5: [(_min(0, 0), _min(6, 0))],                            # Sábado (madrugada del turno viernes)
    6: [],                                                     # Domingo (descanso)
}


def ventanas_por_dia(dow: int, turno: str):
    """Devuelve ventanas (minutos) por día según turno."""
    if (turno or "").lower() == "nocturno":
        return _NOCTURNO.get(int(dow), [])
    return _DIURNO.get(int(dow), [])


def esta_en_ventana(dt: datetime, turno: str) -> bool:
    if not dt:
        return False
    dow = dt.weekday()
    minutos = dt.hour * 60 + dt.minute
    for ini, fin in ventanas_por_dia(dow, turno):
        if ini <= minutos < fin:
            return True
    return False


def fin_ventana_actual(dt: datetime, turno: str):
    """
    Devuelve datetime del fin del turno actual.

    El turno nocturno cruza la medianoche y está representado en dos ventanas
    diarias. Cuando la tarea inicia en el tramo de la noche, su fin real es el
    final del tramo de madrugada del día siguiente (06:00), no las 00:00.
    Si no está dentro de una ventana, devuelve None.
    """
    if not dt:
        return None
    dow = dt.weekday()
    minutos = dt.hour * 60 + dt.minute
    for ini, fin in ventanas_por_dia(dow, turno):
        if ini <= minutos < fin:
            if fin == 1440:
                medianoche = datetime.combine(dt.date(), time(0, 0)) + timedelta(days=1)
                if (turno or "").lower() == "nocturno":
                    ventanas_siguiente = ventanas_por_dia((dow + 1) % 7, turno)
                    for sig_ini, sig_fin in ventanas_siguiente:
                        if sig_ini != 0:
                            continue
                        if sig_fin == 1440:
                            return medianoche + timedelta(days=1)
                        return medianoche + timedelta(minutes=sig_fin)
                return medianoche
            fin_h = fin // 60
            fin_m = fin % 60
            return datetime.combine(dt.date(), time(fin_h, fin_m))

    # FIN AUTO debe existir siempre, incluso en días sin ventana configurada.
    # Se usa la franja horaria operativa correspondiente al momento de inicio.
    if (turno or "").lower() == "nocturno":
        if minutos < _min(6, 0):
            return datetime.combine(dt.date(), time(6, 0))
        return datetime.combine(dt.date() + timedelta(days=1), time(6, 0))
    if minutos < _min(14, 0):
        return datetime.combine(dt.date(), time(14, 0))
    return datetime.combine(dt.date(), time(22, 0))


def requiere_nuevo_tramo(dt_inicio: datetime, dt_ahora: datetime, turno: str = None) -> bool:
    """Indica si el turno en el que inicio el tramo ya termino."""
    if not dt_inicio or not dt_ahora or dt_ahora < dt_inicio:
        return False
    turno = turno or inferir_turno(dt_inicio)
    fin_turno = fin_ventana_actual(dt_inicio, turno)
    return bool(fin_turno and dt_ahora >= fin_turno)

def truncar_a_minuto(dt: datetime):
    """Devuelve el mismo datetime sin segundos ni microsegundos."""
    if not dt:
        return None
    return dt.replace(second=0, microsecond=0)

def ultima_fin_ventana(dt: datetime, turno: str):
    """
    Devuelve el fin de la última ventana laboral <= dt.
    Si no encuentra una ventana válida, devuelve None.
    """
    if not dt:
        return None
    mejor = None
    # buscar hasta 7 días atrás (suficiente para cubrir ciclos)
    for i in range(0, 8):
        dia = dt.date() - timedelta(days=i)
        for ini, fin in ventanas_por_dia(dia.weekday(), turno):
            if fin == 1440:
                fin_dt = datetime.combine(dia, time(0, 0)) + timedelta(days=1)
            else:
                fin_h = fin // 60
                fin_m = fin % 60
                fin_dt = datetime.combine(dia, time(fin_h, fin_m))
            if fin_dt <= dt:
                if (mejor is None) or (fin_dt > mejor):
                    mejor = fin_dt
    return mejor

def sumar_segundos_laborales(dt_inicio: datetime, segundos: int, turno: str = None):
    """
    Devuelve el datetime en que se cumplen N segundos laborables desde dt_inicio.
    Si no encuentra suficientes ventanas, devuelve None.
    """
    if not dt_inicio:
        return None

    restante = max(0, int(segundos or 0))
    if restante <= 0:
        return dt_inicio

    turno = turno or inferir_turno(dt_inicio)
    dia = dt_inicio.date()
    cursor = dt_inicio

    for _ in range(0, 21):
        for ini_min, fin_min in ventanas_por_dia(dia.weekday(), turno):
            ini_h = ini_min // 60
            ini_m = ini_min % 60
            ini_dt = datetime.combine(dia, time(ini_h, ini_m))

            if fin_min == 1440:
                fin_dt = datetime.combine(dia, time(0, 0)) + timedelta(days=1)
            else:
                fin_h = fin_min // 60
                fin_m = fin_min % 60
                fin_dt = datetime.combine(dia, time(fin_h, fin_m))

            if fin_dt <= cursor:
                continue

            start = cursor if cursor > ini_dt else ini_dt
            disponible = int(max(0, (fin_dt - start).total_seconds()))
            if disponible <= 0:
                continue
            if disponible >= restante:
                return start + timedelta(seconds=restante)
            restante -= disponible

        dia = dia + timedelta(days=1)
        cursor = datetime.combine(dia, time(0, 0))

    return None


def fin_autocierre_efectivo(
    dt_inicio: datetime,
    dt_ahora: datetime,
    turno: str = None,
    limite_seg: int = None,
    pausa_acum_seg: int = 0,
    limite_registro_seg: int = None,
):
    """
    Calcula el fin real para autocierre:
    - fin de la ventana/turno donde inicio la tarea, si ya paso;
    - o el momento en que cumple el limite laboral configurado.
    """
    if not dt_inicio or not dt_ahora or dt_ahora < dt_inicio:
        return None

    turno = turno or inferir_turno(dt_inicio)
    candidatos = []

    fin_turno = fin_ventana_actual(dt_inicio, turno)
    if fin_turno and dt_ahora >= fin_turno:
        candidatos.append(fin_turno)

    if limite_seg is not None:
        pausa_seg = max(0, int(pausa_acum_seg or 0))
        fin_disparo = sumar_segundos_laborales(dt_inicio, int(limite_seg or 0) + pausa_seg, turno)
        if fin_disparo and dt_ahora >= fin_disparo:
            registro_seg = int(limite_registro_seg if limite_registro_seg is not None else limite_seg)
            fin_registro = sumar_segundos_laborales(dt_inicio, registro_seg + pausa_seg, turno)
            candidatos.append(fin_registro or fin_disparo)

    if not candidatos:
        return None

    return truncar_a_minuto(min(candidatos))


def iso_sin_segundos(raw):
    """Normaliza un valor ISO a 'YYYY-MM-DD HH:MM:00' si puede parsearlo."""
    try:
        dt = datetime.fromisoformat(str(raw or "").replace("Z", "").strip())
    except Exception:
        return str(raw or "").strip()
    return truncar_a_minuto(dt).strftime("%Y-%m-%d %H:%M:%S")

def inferir_turno(dt_inicio: datetime) -> str:
    """
    Inferir turno con base en la hora de inicio:
    - Si cae dentro de una ventana nocturna para ese día -> 'nocturno'
    - Si no, 'diurno'
    """
    try:
        if not dt_inicio:
            return "diurno"
        dow = dt_inicio.weekday()
        minutos = dt_inicio.hour * 60 + dt_inicio.minute
        for ini, fin in ventanas_por_dia(dow, "nocturno"):
            if ini <= minutos < fin:
                return "nocturno"

        # Respaldo por franja horaria para días sin turno configurado.
        inicio_noche = _min(21, 30) if dow == 4 else _min(20, 30)
        if minutos < _min(6, 0) or minutos >= inicio_noche:
            return "nocturno"
    except Exception:
        pass
    return "diurno"


def segundos_laborales_transcurridos(dt_inicio: datetime, dt_fin: datetime, turno: str = None) -> int:
    """
    Segundos laborables entre dt_inicio y dt_fin, según turno.
    """
    if not dt_inicio or not dt_fin:
        return 0
    if dt_fin <= dt_inicio:
        return 0

    turno = turno or inferir_turno(dt_inicio)
    total = 0

    dia = dt_inicio.date()
    fin = dt_fin.date()

    while dia <= fin:
        dow = dia.weekday()
        ventanas = ventanas_por_dia(dow, turno)
        for ini_min, fin_min in ventanas:
            ini_h = ini_min // 60
            ini_m = ini_min % 60

            if fin_min == 1440:
                fin_dt = datetime.combine(dia + timedelta(days=1), time(0, 0))
            else:
                fin_h = fin_min // 60
                fin_m = fin_min % 60
                fin_dt = datetime.combine(dia, time(fin_h, fin_m))

            ini_dt = datetime.combine(dia, time(ini_h, ini_m))

            start = dt_inicio if dt_inicio > ini_dt else ini_dt
            end = dt_fin if dt_fin < fin_dt else fin_dt

            if end > start:
                total += (end - start).total_seconds()

        dia = dia + timedelta(days=1)

    return int(max(0, total))
