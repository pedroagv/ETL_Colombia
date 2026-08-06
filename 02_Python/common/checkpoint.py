"""Checkpoint/idempotencia basados en `etl_control_carga` y `etl_checkpoint`
(ver 01_SQL/04_Importaciones.sql). Reanudar un proceso interrumpido es
siempre: "pedir los archivos que todavía no tengan SUCCESS para esta fase".
"""
import time
from datetime import datetime


def archivos_pendientes(conn, tabla_origen: str, fase: str) -> list[str]:
    try:
        with conn.cursor() as cursor:
            # 1. Si la tabla origen no existe en MySQL, retornar [] de inmediato (0.1ms)
            cursor.execute("SHOW TABLES LIKE %s", (tabla_origen,))
            if not cursor.fetchone():
                return []

            # 2. Si la tabla está completamente vacía, retornar [] de inmediato (0.1ms)
            cursor.execute(f"SELECT 1 FROM `{tabla_origen}` LIMIT 1")
            if not cursor.fetchone():
                return []

            # 3. Si etl_control_carga no existe aún, todos los archivos en la tabla origen están pendientes
            cursor.execute("SHOW TABLES LIKE 'etl_control_carga'")
            if not cursor.fetchone():
                cursor.execute(f"SELECT DISTINCT archivo_origen FROM `{tabla_origen}` WHERE archivo_origen IS NOT NULL")
                return [row[0] for row in cursor.fetchall() if row[0]]

            # 4. Consulta optimizada de pendientes
            sql = f"""
                SELECT d.archivo_origen
                FROM (
                    SELECT DISTINCT archivo_origen
                    FROM `{tabla_origen}`
                    WHERE archivo_origen IS NOT NULL
                ) d
                WHERE NOT EXISTS (
                    SELECT 1 FROM etl_control_carga c
                    WHERE c.tabla_origen = %s AND c.archivo_origen = d.archivo_origen
                      AND c.fase = %s AND c.estado = 'SUCCESS'
                )
                ORDER BY d.archivo_origen
            """
            cursor.execute(sql, (tabla_origen, fase))
            return [row[0] for row in cursor.fetchall()]
    except Exception:
        return []





def ensure_control_carga(conn):
    sql = """
    CREATE TABLE IF NOT EXISTS `etl_control_carga` (
      `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
      `tabla_origen`          VARCHAR(64) NOT NULL,
      `archivo_origen`        VARCHAR(255) NOT NULL,
      `fase`                  VARCHAR(30) NOT NULL,
      `estado`                VARCHAR(20) NOT NULL,
      `registros_procesados`  INT UNSIGNED NULL,
      `fecha_inicio`          DATETIME NULL,
      `fecha_fin`             DATETIME NULL,
      `tiempo_ejecucion_seg`  DECIMAL(10,2) NULL,
      `mensaje_error`         TEXT NULL,
      UNIQUE KEY `uq_etl_control_carga` (`tabla_origen`, `archivo_origen`, `fase`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    with conn.cursor() as cursor:
        cursor.execute(sql)
    conn.commit()


def marcar_inicio(conn, tabla_origen: str, archivo_origen: str, fase: str):
    ensure_control_carga(conn)
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
