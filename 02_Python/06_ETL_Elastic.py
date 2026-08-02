"""
Fase 6/7: indexación incremental en Elasticsearch, vía TradeIntelligence.

IMPORTANTE - decisión de arquitectura (ver Arquitectura.md → "Contrato de
integración con TradeIntelligence"): el mapping de Elasticsearch (Fase 6) y
el pipeline de indexación con Bulk API (Fase 7) YA EXISTEN en
TradeIntelligence (`trade_data.elastic.mapping` / `trade_data.indexing.
pipeline`), generados dinámicamente desde `trade_data_campoelastic` para
CUALQUIER tabla de CUALQUIER país. Reimplementar un segundo indexador aquí
crearía dos pipelines independientes indexando la misma tabla con
convenciones de nombre de índice distintas: en vez de eso, este script
dispara el pipeline YA EXISTENTE (vía `manage.py run_indexing`, en
subprocess) de forma INCREMENTAL: sólo pide las filas de `importacion` con
`id` mayor al último checkpoint guardado en `colombia.etl_checkpoint`
(usa `--min-id`, agregado a TradeIntelligence para este propósito).

Esto es lo que permite "meter un archivo, mandarlo a indexar, e ir
liberando": 04_ETL_Importaciones.py inserta las filas de un archivo, y
este script indexa INMEDIATAMENTE sólo esas filas nuevas (no vuelve a leer
ni reenviar todo el histórico en cada corrida), quedando ese archivo
disponible en Elasticsearch antes de pasar al siguiente.
"""
import subprocess
import sys

from common import config, db
from common.logging_setup import get_logger

logger = get_logger("dw_elastic", "dian_dw_elastic.log")

PROCESO_CHECKPOINT = "elastic_importacion"


def _obtener_checkpoint(conn) -> int:
    with conn.cursor() as cursor:
        cursor.execute("SELECT ultimo_id_procesado FROM etl_checkpoint WHERE proceso = %s", (PROCESO_CHECKPOINT,))
        row = cursor.fetchone()
        return row[0] if row else 0


def _obtener_max_id(conn) -> int:
    with conn.cursor() as cursor:
        cursor.execute("SELECT COALESCE(MAX(id), 0) FROM `importacion`")
        return cursor.fetchone()[0]


def _actualizar_checkpoint(conn, nuevo_max_id: int, registros_nuevos: int):
    with conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE etl_checkpoint
            SET ultimo_id_procesado = %s, registros_totales = registros_totales + %s
            WHERE proceso = %s
            """,
            (nuevo_max_id, registros_nuevos, PROCESO_CHECKPOINT),
        )
    conn.commit()


def indexar_incremental(chunk_size: int = 2000, limit: int | None = None) -> bool:
    if not config.TRADE_INTELLIGENCE_DIR or not config.TRADE_INTELLIGENCE_PYTHON:
        logger.warning(
            "TRADE_INTELLIGENCE_DIR/TRADE_INTELLIGENCE_PYTHON no configurados en .env: "
            "se omite la indexación (configúralos para activar la integración)."
        )
        return False

    conn = db.get_connection(database=config.MYSQL_DATABASE)
    try:
        checkpoint_actual = _obtener_checkpoint(conn)
        max_id = _obtener_max_id(conn)

        if max_id <= checkpoint_actual:
            logger.info(f"Nada nuevo para indexar (checkpoint={checkpoint_actual}, max_id={max_id}).")
            return True

        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM `importacion` WHERE id > %s", (checkpoint_actual,))
            registros_nuevos = cursor.fetchone()[0]

        cmd = [
            config.TRADE_INTELLIGENCE_PYTHON, "manage.py", "run_indexing",
            config.TI_ESQUEMA, config.TI_TABLA_IMPORTACION,
            "--chunk-size", str(chunk_size), "--min-id", str(checkpoint_actual),
        ]
        if limit is not None:
            cmd.extend(["--limit", str(limit)])

        logger.info(f"Indexando {registros_nuevos} fila(s) nueva(s) (id > {checkpoint_actual})...")
        resultado = subprocess.run(cmd, cwd=config.TRADE_INTELLIGENCE_DIR, capture_output=True, text=True)
        for linea in resultado.stdout.splitlines():
            logger.info(f"[run_indexing] {linea}")
        if resultado.returncode != 0:
            logger.error(f"run_indexing falló (código {resultado.returncode}): {resultado.stderr}")
            return False

        _actualizar_checkpoint(conn, max_id, registros_nuevos)
        logger.info(f"Checkpoint de indexación actualizado a id={max_id}.")
        return True
    finally:
        conn.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Fase 6/7: indexación incremental en Elasticsearch (vía TradeIntelligence).")
    parser.add_argument("--chunk-size", type=int, default=2000)
    parser.add_argument("--limit", type=int, default=None, help="Sólo para pruebas: limita filas leídas del origen.")
    args = parser.parse_args()

    logger.info("=== Iniciando Fase 6: Indexación Elasticsearch ===")
    ok = indexar_incremental(chunk_size=args.chunk_size, limit=args.limit)
    logger.info("=== Fase 6 completada ===" if ok else "=== Fase 6 finalizó con advertencias/errores ===")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
