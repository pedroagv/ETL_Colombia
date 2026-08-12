"""Inserta tareas en la cola compartida `trade_intelligence`.`cola_indexacion`
(ver TradeIntelligence: trade_data.models.ColaIndexacion) cuando un archivo
termina de cargarse en la tabla física de hechos. El worker de consola del
proyecto 'indexacion' (corrido por cron) la procesa: ejecuta el SP indicado
con el archivo como parámetro y manda el resultado a Elasticsearch.

Misma conexión que usa el resto de la Fase 4 (`colombia`): basta con
calificar la tabla como `trade_intelligence`.`cola_indexacion`, sin abrir
una conexión nueva, porque ambas bases viven en el mismo servidor MySQL.
"""

PROCEDIMIENTO_IMPORTACION = "sp_extraer_importacion_por_archivo"
PROCEDIMIENTO_EXPORTACION = "sp_extraer_exportacion_por_archivo"


def _anio_predominante(conn, tabla: str, archivo: str) -> int:
    """El worker indexa el archivo completo en un único índice, así que
    necesita un solo año por tarea. `anio` sale de la fecha real
    de cada declaración, no del nombre del archivo: se usa el año con más filas."""
    with conn.cursor() as cursor:
        cursor.execute(
            f"SELECT anio FROM `{tabla}` WHERE archivo_origen = %s "
            "GROUP BY anio ORDER BY COUNT(*) DESC LIMIT 1",
            (archivo,),
        )
        fila = cursor.fetchone()
    return fila[0] if fila else None


def encolar_importacion(conn, archivo: str) -> None:
    anio = _anio_predominante(conn, "importacion", archivo)
    with conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO `trade_intelligence`.`cola_indexacion` "
            "(pais, tipo_intercambio, procedimiento_almacenado, archivo, anio, estado, "
            "detalle, fecha, fecha_actualizacion) "
            "VALUES (%s, %s, %s, %s, %s, 'PENDIENTE', '', NOW(6), NOW(6))",
            ("colombia", "IMPORTACION", PROCEDIMIENTO_IMPORTACION, archivo, anio),
        )
    conn.commit()


def encolar_exportacion(conn, archivo: str) -> None:
    anio = _anio_predominante(conn, "exportacion", archivo)
    with conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO `trade_intelligence`.`cola_indexacion` "
            "(pais, tipo_intercambio, procedimiento_almacenado, archivo, anio, estado, "
            "detalle, fecha, fecha_actualizacion) "
            "VALUES (%s, %s, %s, %s, %s, 'PENDIENTE', '', NOW(6), NOW(6))",
            ("colombia", "EXPORTACION", PROCEDIMIENTO_EXPORTACION, archivo, anio),
        )
    conn.commit()

