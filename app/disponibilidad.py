"""
Cálculo de horarios disponibles. Funciones puras (sin base de datos ni Flask),
lo que permite probarlas de forma aislada.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta


def _hora(texto: str) -> time:
    h, m = texto.split(":")
    return time(int(h), int(m))


def bloques_del_dia(cfg: dict, dia: date) -> list[tuple[datetime, datetime]]:
    """Tramos de atención de un día, según la configuración del negocio."""
    tramos = cfg["horarios"].get(str(dia.weekday()), [])
    return [(datetime.combine(dia, _hora(a)), datetime.combine(dia, _hora(b))) for a, b in tramos]


def se_solapan(inicio_a: datetime, fin_a: datetime, inicio_b: datetime, fin_b: datetime) -> bool:
    return inicio_a < fin_b and inicio_b < fin_a


def horarios_disponibles(
    cfg: dict,
    dia: date,
    duracion: int,
    ocupados: list[tuple[datetime, datetime]],
    ahora: datetime,
) -> list[datetime]:
    """
    Devuelve los inicios posibles para una reserva de `duracion` minutos en `dia`.

    - Respeta el horario de atención (la reserva debe terminar antes del cierre).
    - No se solapa con reservas existentes (`ocupados`).
    - Respeta la anticipación mínima y máxima configurada.
    """
    if dia < ahora.date() or dia > ahora.date() + timedelta(days=cfg["dias_anticipacion"]):
        return []
    paso = timedelta(minutes=cfg["intervalo_minutos"])
    largo = timedelta(minutes=duracion)
    limite_aviso = ahora + timedelta(minutes=cfg["minutos_minimos_aviso"])
    libres = []
    for apertura, cierre in bloques_del_dia(cfg, dia):
        inicio = apertura
        while inicio + largo <= cierre:
            fin = inicio + largo
            if inicio >= limite_aviso and not any(se_solapan(inicio, fin, a, b) for a, b in ocupados):
                libres.append(inicio)
            inicio += paso
    return libres


def es_horario_valido(cfg: dict, inicio: datetime, duracion: int,
                      ocupados: list[tuple[datetime, datetime]], ahora: datetime) -> bool:
    """Valida en el servidor un horario elegido por el cliente (nunca confiar en el navegador)."""
    return inicio in horarios_disponibles(cfg, inicio.date(), duracion, ocupados, ahora)
