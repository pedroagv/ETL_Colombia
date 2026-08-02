import logging
import sys

from . import config


def get_logger(nombre_proceso: str, archivo_log: str) -> logging.Logger:
    """Logger consistente con el estilo de 01_fase_descarga.py/02_fase_sql.py:
    mismo formato, mismo doble destino (archivo + stdout)."""
    level = getattr(logging, config.LOG_LEVEL, logging.INFO)
    logger = logging.getLogger(nombre_proceso)
    if logger.handlers:
        return logger  # ya configurado (p.ej. al reimportar en tests)

    logger.setLevel(level)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    file_handler = logging.FileHandler(archivo_log, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger
