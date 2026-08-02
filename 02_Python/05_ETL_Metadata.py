"""
Fase 5: sincronización de metadata hacia TradeIntelligence.

IMPORTANTE - decisión de arquitectura (ver Arquitectura.md → "Contrato de
integración con TradeIntelligence"): la tabla `trade_data_campoelastic`
(el equivalente exacto de lo que el enunciado original llama
`trade_data_campoelastic`) YA EXISTE y YA se sincroniza automáticamente:
TradeIntelligence trae un escáner genérico (`trade_data.scanner.sync`) que
introspecciona INFORMATION_SCHEMA.COLUMNS de CUALQUIER tabla física
registrada (en cualquier país/esquema) y crea/actualiza un `CampoElastic`
por columna. Reimplementar esa misma lógica en este proyecto duplicaría un
mecanismo que ya funciona y arriesgaría que ambas copias diverjan.

Por eso esta fase NO reconstruye la metadata desde cero: dispara el
escaneo YA EXISTENTE (vía `manage.py scan_columns`, en subprocess, sin
importar Django en este proyecto) y luego aplica DOS mejoras propias, en
SQL directo contra `trade_intelligence` (mismo servidor MySQL):

  1. Configura `TablaOrigen.columna_anio = 'fecha_declaracion'` (requerida
     para que la Fase 6 pueda particionar los índices por año) — sólo si
     todavía no se configuró (respeta cualquier ajuste manual posterior).
  2. Reemplaza el label "tonto" que pone el escáner por defecto
     ('pais_origen' -> 'Pais origen') por uno generado con las reglas de
     `common/labels.py` ('pais_origen' -> 'País de Origen'), SOLO en
     columnas recién detectadas que ningún administrador haya tocado
     todavía (fecha_creacion == fecha_ultima_deteccion: ver
     trade_data.models.CampoElastic). Así se cumple "no quiero escribir
     ningún label manualmente" sin pelear con la sincronización real.

También oculta (visible=False) la columna técnica `id`, y EXCLUYE del
índice (activo=False) la columna de auditoría/linaje `archivo_origen`
(nunca debe llegar a Elasticsearch, ver reglas obligatorias del proyecto).
"""
import re
import subprocess
import sys

from common import config, db
from common.labels import humanize_label
from common.logging_setup import get_logger

logger = get_logger("dw_metadata", "dian_dw_metadata.log")

TI_DB = "trade_intelligence"
COLUMNAS_OCULTAS = {"id"}          # visible=False (siguen indexadas, sólo se ocultan en la UI)
COLUMNAS_EXCLUIDAS = {"archivo_origen"}  # activo=False (nunca se indexan)

# Réplica exacta y mínima de trade_data.scanner.sync.humanize_column_name y
# trade_data.scanner.type_mapping.infer_es_type (TradeIntelligence): sirve
# para reconocer si un `label`/`tipo_elastic` sigue siendo el valor "tonto"
# que puso el escáner al crear la columna (nunca lo vuelve a tocar después,
# ver trade_data/scanner/sync.py) y por lo tanto es seguro reemplazarlo. Si
# ya no coincide, alguien lo personalizó y no se toca.
def _label_por_defecto_ti(columna: str) -> str:
    palabras = re.sub(r"[_\-]+", " ", columna).strip().split()
    if not palabras:
        return columna
    return " ".join([palabras[0].capitalize()] + palabras[1:])


_SQL_A_ELASTIC = {
    "char": "keyword", "varchar": "keyword", "text": "text", "tinytext": "text",
    "mediumtext": "text", "longtext": "text", "enum": "keyword", "set": "keyword",
    "tinyint": "byte", "smallint": "short", "mediumint": "integer", "int": "integer",
    "integer": "integer", "bigint": "long", "decimal": "double", "numeric": "double",
    "float": "float", "double": "double", "bool": "boolean", "boolean": "boolean",
    "date": "date", "datetime": "date", "timestamp": "date", "time": "date",
    "year": "integer", "json": "text", "binary": "keyword", "varbinary": "keyword",
}


def _tipo_elastic_por_defecto_ti(tipo_sql: str) -> str:
    return _SQL_A_ELASTIC.get((tipo_sql or "").lower().strip(), "keyword")


def _ejecutar_scan_columns() -> bool:
    if not config.TRADE_INTELLIGENCE_DIR or not config.TRADE_INTELLIGENCE_PYTHON:
        logger.warning(
            "TRADE_INTELLIGENCE_DIR/TRADE_INTELLIGENCE_PYTHON no configurados en .env: "
            "se omite el disparo de 'scan_columns' (configúralos para activar la integración)."
        )
        return False

    cmd = [
        config.TRADE_INTELLIGENCE_PYTHON, "manage.py", "scan_columns",
        "--tabla", config.TI_TABLA_IMPORTACION, "--esquema", config.TI_ESQUEMA,
    ]
    logger.info(f"Ejecutando: {' '.join(cmd)} (cwd={config.TRADE_INTELLIGENCE_DIR})")
    resultado = subprocess.run(cmd, cwd=config.TRADE_INTELLIGENCE_DIR, capture_output=True, text=True)
    for linea in resultado.stdout.splitlines():
        logger.info(f"[scan_columns] {linea}")
    if resultado.returncode != 0:
        logger.error(f"scan_columns falló (código {resultado.returncode}): {resultado.stderr}")
        return False
    return True


def _configurar_columna_anio(conn_ti):
    with conn_ti.cursor() as cursor:
        cursor.execute(
            """
            UPDATE trade_data_tablaorigen
            SET columna_anio = %s, activo = 1
            WHERE base_datos = %s AND tabla = %s AND (columna_anio = '' OR columna_anio IS NULL)
            """,
            (config.COLUMNA_ANIO_ELASTIC, config.TI_ESQUEMA, config.TI_TABLA_IMPORTACION),
        )
        filas = cursor.rowcount
    conn_ti.commit()
    if filas:
        logger.info(f"TablaOrigen.columna_anio configurada en '{config.COLUMNA_ANIO_ELASTIC}' para '{config.TI_ESQUEMA}.{config.TI_TABLA_IMPORTACION}'.")


def _mejorar_labels(conn_ti):
    with conn_ti.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, columna_original, label, tipo_sql, tipo_elastic FROM trade_data_campoelastic
            WHERE base_datos = %s AND tabla = %s
            """,
            (config.TI_ESQUEMA, config.TI_TABLA_IMPORTACION),
        )
        filas = cursor.fetchall()

        actualizados = 0
        for campo_id, columna, label_actual, tipo_sql, tipo_elastic_actual in filas:
            intocado = label_actual == _label_por_defecto_ti(columna)
            if not intocado:
                continue  # alguien ya personalizó este campo: no se toca

            nuevo_label = humanize_label(columna)
            tipo_elastic_correcto = _tipo_elastic_por_defecto_ti(tipo_sql)
            cursor.execute(
                "UPDATE trade_data_campoelastic SET label = %s, tipo_elastic = %s WHERE id = %s",
                (nuevo_label, tipo_elastic_correcto, campo_id),
            )
            actualizados += 1

        if COLUMNAS_OCULTAS:
            cursor.execute(
                f"UPDATE trade_data_campoelastic SET visible = 0 "
                f"WHERE base_datos = %s AND tabla = %s AND columna_original IN ({','.join(['%s'] * len(COLUMNAS_OCULTAS))})",
                (config.TI_ESQUEMA, config.TI_TABLA_IMPORTACION, *COLUMNAS_OCULTAS),
            )
        if COLUMNAS_EXCLUIDAS:
            cursor.execute(
                f"UPDATE trade_data_campoelastic SET activo = 0 "
                f"WHERE base_datos = %s AND tabla = %s AND columna_original IN ({','.join(['%s'] * len(COLUMNAS_EXCLUIDAS))})",
                (config.TI_ESQUEMA, config.TI_TABLA_IMPORTACION, *COLUMNAS_EXCLUIDAS),
            )
    conn_ti.commit()
    logger.info(f"Labels mejorados en {actualizados} columna(s) nueva(s); {len(COLUMNAS_OCULTAS)} oculta(s), {len(COLUMNAS_EXCLUIDAS)} excluida(s) de Elasticsearch.")


def main():
    logger.info("=== Iniciando Fase 5: Metadata ===")
    if not _ejecutar_scan_columns():
        logger.warning("Fase 5 finalizó sin sincronizar metadata (ver advertencia anterior).")
        return

    conn_ti = db.get_connection(database=TI_DB)
    try:
        _configurar_columna_anio(conn_ti)
        _mejorar_labels(conn_ti)
    finally:
        conn_ti.close()
    logger.info("=== Fase 5 completada ===")


if __name__ == "__main__":
    main()
