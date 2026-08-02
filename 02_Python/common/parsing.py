"""Parseo tolerante de los valores crudos (TEXT) de `temporal_impo` hacia
tipos nativos de Python, usado por 04_ETL_Importaciones.py al construir cada
fila de `importacion`. Nunca lanza excepción por un valor sucio: un dato
inválido se resuelve a None (NULL) en vez de tumbar el chunk completo.
"""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


def parse_fecha(valor) -> date | None:
    """Fechas de la DIAN llegan como texto 'YYYYMMDD' (ej. '20180115')."""
    if not valor:
        return None
    texto = str(valor).strip()
    if len(texto) != 8 or not texto.isdigit():
        return None
    try:
        return datetime.strptime(texto, "%Y%m%d").date()
    except ValueError:
        return None


def primera_fecha_valida(*valores) -> date | None:
    for valor in valores:
        fecha = parse_fecha(valor)
        if fecha is not None:
            return fecha
    return None


def parse_decimal(valor, default=None):
    if valor is None or valor == "":
        return default
    try:
        return Decimal(str(valor).strip())
    except (InvalidOperation, ValueError):
        return default


def parse_entero(valor, default=None):
    dec = parse_decimal(valor)
    if dec is None:
        return default
    try:
        return int(dec)
    except (ValueError, OverflowError):
        return default


def limpio(valor) -> str | None:
    """Trim + colapso de vacíos a None; deja el resto del texto tal cual."""
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto or None
