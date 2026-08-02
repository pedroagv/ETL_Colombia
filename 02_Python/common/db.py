"""Acceso a MySQL para las Fases 3-4. Envoltorio delgado sobre pymysql: nunca
ORM, nunca un pool de conexiones propio (a este volumen, una conexión por
fase/archivo procesado es más simple y suficientemente rápido).
"""
import pymysql
from contextlib import contextmanager

from . import config


def get_connection(database: str | None = None):
    return pymysql.connect(
        host=config.MYSQL_HOST,
        port=config.MYSQL_PORT,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        database=database or config.MYSQL_DATABASE,
        charset="utf8mb4",
        autocommit=False,
    )


@contextmanager
def connection():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def load_dict(conn, sql: str, params=None) -> dict:
    """Ejecuta `sql` (debe devolver exactamente 2 columnas: clave, id) y
    arma un diccionario {clave: id} en memoria. Es el único mecanismo de
    resolución de dimensiones de todo el proyecto: se carga UNA vez por
    ejecución del ETL, nunca con un SELECT por fila."""
    with conn.cursor() as cursor:
        cursor.execute(sql, params or ())
        return {row[0]: row[1] for row in cursor.fetchall()}


def fetch_all_dicts(conn, sql: str, params=None) -> list[dict]:
    with conn.cursor() as cursor:
        cursor.execute(sql, params or ())
        columnas = [d[0] for d in cursor.description]
        return [dict(zip(columnas, row)) for row in cursor.fetchall()]
