"""Checkpoint/idempotencia basados en `etl_control_carga` y `etl_checkpoint`
(ver 01_SQL/04_Importaciones.sql). Reanudar un proceso interrumpido es
siempre: "pedir los archivos que todavía no tengan SUCCESS para esta fase".
"""
import time
from datetime import datetime


def archivos_pendientes(conn, tabla_origen: str, fase: str) -> list[str]:
    """Archivos presentes en `tabla_origen` (temporal_impo/temporal_expo) que
    aún no tienen un registro SUCCESS para `fase` en etl_control_carga. Usa el
    índice existente sobre archivo_origen (ver database.py::ensure_index) para
    no escanear la tabla completa."""
    sql = f"""
        SELECT DISTINCT t.archivo_origen
        FROM `{tabla_origen}` t
        LEFT JOIN etl_control_carga c
          ON c.tabla_origen = %s AND c.archivo_origen = t.archivo_origen
         AND c.fase = %s AND c.estado = 'SUCCESS'
        WHERE t.archivo_origen IS NOT NULL AND c.id IS NULL
        ORDER BY t.archivo_origen
    """
    with conn.cursor() as cursor:
        cursor.execute(sql, (tabla_origen, fase))
        return [row[0] for row in cursor.fetchall()]


def marcar_inicio(conn, tabla_origen: str, archivo_origen: str, fase: str):
    sql = """
        INSERT INTO etl_control_carga (tabla_origen, archivo_origen, fase, estado, fecha_inicio)
        VALUES (%s, %s, %s, 'EN_PROCESO', %s)
        ON DUPLICATE KEY UPDATE estado = 'EN_PROCESO', fecha_inicio = VALUES(fecha_inicio),
            fecha_fin = NULL, mensaje_error = NULL
    """
    with conn.cursor() as cursor:
        cursor.execute(sql, (tabla_origen, archivo_origen, fase, datetime.now()))
    conn.commit()
    return time.monotonic()


def marcar_exito(conn, tabla_origen: str, archivo_origen: str, fase: str, registros: int, inicio_monotonic: float):
    tiempo_seg = round(time.monotonic() - inicio_monotonic, 2)
    sql = """
        UPDATE etl_control_carga
        SET estado = 'SUCCESS', registros_procesados = %s, fecha_fin = %s, tiempo_ejecucion_seg = %s
        WHERE tabla_origen = %s AND archivo_origen = %s AND fase = %s
    """
    with conn.cursor() as cursor:
        cursor.execute(sql, (registros, datetime.now(), tiempo_seg, tabla_origen, archivo_origen, fase))
    conn.commit()


def marcar_error(conn, tabla_origen: str, archivo_origen: str, fase: str, mensaje: str):
    sql = """
        UPDATE etl_control_carga
        SET estado = 'ERROR', fecha_fin = %s, mensaje_error = %s
        WHERE tabla_origen = %s AND archivo_origen = %s AND fase = %s
    """
    with conn.cursor() as cursor:
        cursor.execute(sql, (datetime.now(), mensaje[:60000], tabla_origen, archivo_origen, fase))
    conn.commit()
