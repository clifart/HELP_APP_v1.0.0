from datetime import datetime, time, timedelta


def _min(h, m):
    return int(h) * 60 + int(m)


_DIURNO = {
    0: [(_min(6, 0), _min(22, 0))],   # Lunes
    1: [(_min(6, 0), _min(22, 0))],   # Martes
    2: [(_min(6, 0), _min(22, 0))],   # Miércoles
    3: [(_min(6, 0), _min(22, 0))],   # Jueves
    4: [(_min(6, 0), _min(22, 0))],   # Viernes
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
    Devuelve datetime del fin de la ventana actual.
    Si no está dentro de una ventana, devuelve None.
    """
    if not dt:
        return None
    dow = dt.weekday()
    minutos = dt.hour * 60 + dt.minute
    for ini, fin in ventanas_por_dia(dow, turno):
        if ini <= minutos < fin:
            if fin == 1440:
                return datetime.combine(dt.date(), time(0, 0)) + timedelta(days=1)
            fin_h = fin // 60
            fin_m = fin % 60
            return datetime.combine(dt.date(), time(fin_h, fin_m))
    return None


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
