import argparse
import os
import sys
import time
import signal
import logging
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "02_Python"))
from common import db, checkpoint  # noqa: E402  (requiere el sys.path.insert de arriba)

logger = logging.getLogger("main_etl")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

running = True

def handle_signal(sig, frame):
    global running
    logger.info(f"Señación {sig} recibida. Deteniendo el servicio ETL...")
    running = False

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)

def run_phase_1(limit_months=None):
    logger.info("Ejecutando Fase 1: Descarga de estadísticas DIAN...")
    cmd = [sys.executable, "02_Python/01_ETL_Descarga.py"]
    if limit_months:
        cmd.extend(["--limit-months", str(limit_months)])
    res = subprocess.run(cmd)
    if res.returncode != 0:
        logger.error("Error en la ejecución de la Fase 1.")
        return False
    return True

def run_phase_2(limit_files=None):
    logger.info("Ejecutando Fase 2: Procesamiento ETL e Inserción en MySQL (tabla temporal)...")
    cmd = [sys.executable, "02_Python/02_ETL_SQL.py"]
    if limit_files:
        cmd.extend(["--limit-files", str(limit_files)])
    res = subprocess.run(cmd)
    if res.returncode != 0:
        logger.error("Error en la ejecución de la Fase 2.")
        return False
    return True

def run_phase_3(archivo=None):
    logger.info(f"Ejecutando Fase 3: Dimensiones{f' (archivo={archivo})' if archivo else ''}...")
    cmd = [sys.executable, "02_Python/03_ETL_Dimensiones.py"]
    if archivo:
        cmd.extend(["--archivo", archivo])
    res = subprocess.run(cmd)
    if res.returncode != 0:
        logger.error("Error en la ejecución de la Fase 3.")
        return False
    return True

def run_phase_4(archivo=None):
    logger.info(f"Ejecutando Fase 4: tabla 'importacion'{f' (archivo={archivo})' if archivo else ''}...")
    cmd = [sys.executable, "02_Python/04_ETL_Importaciones.py"]
    if archivo:
        cmd.extend(["--archivo", archivo])
    res = subprocess.run(cmd)
    if res.returncode != 0:
        logger.error("Error en la ejecución de la Fase 4.")
        return False
    return True

def run_phase_5():
    logger.info("Ejecutando Fase 5: Sincronización de metadata en TradeIntelligence...")
    res = subprocess.run([sys.executable, "02_Python/05_ETL_Metadata.py"])
    if res.returncode != 0:
        logger.error("Error en la ejecución de la Fase 5.")
        return False
    return True

def run_phase_6():
    logger.info("Ejecutando Fase 6: Indexación incremental en Elasticsearch (vía TradeIntelligence)...")
    res = subprocess.run([sys.executable, "02_Python/06_ETL_Elastic.py"])
    if res.returncode != 0:
        logger.error("Error en la ejecución de la Fase 6.")
        return False
    return True

def run_dw_pipeline():
    """Orquesta las Fases 3-6 ARCHIVO POR ARCHIVO: por cada archivo pendiente
    se construyen sus dimensiones, se carga en 'importacion' y se indexa de
    inmediato en Elasticsearch (incremental, sólo lo nuevo) antes de pasar
    al siguiente -- así cada archivo queda disponible para consulta apenas
    termina, sin esperar a que se procese todo el histórico ('ir liberando',
    según lo pedido)."""
    run_phase_5()  # metadata: no cambia por archivo, se sincroniza una sola vez

    conn = db.get_connection(database="colombia")
    try:
        pendientes = checkpoint.archivos_pendientes(conn, "temporal_impo", "HECHOS")
    finally:
        conn.close()

    if not pendientes:
        logger.info("No hay archivos pendientes para el Data Warehouse (Fases 3-6).")
        return

    logger.info(f"{len(pendientes)} archivo(s) pendiente(s): se procesan uno a uno, liberando cada uno a Elasticsearch.")
    for archivo in pendientes:
        if not running:
            break
        logger.info(f"=== Procesando '{archivo}' (dimensiones -> hechos -> índice) ===")
        if run_phase_3(archivo) and run_phase_4(archivo):
            run_phase_6()
            logger.info(f"=== '{archivo}' liberado: ya está en 'importacion' y en Elasticsearch ===")
        else:
            logger.error(f"'{archivo}' quedó incompleto; se reintentará en la próxima corrida.")

def execute_etl_flow(args):
    if args.download_only:
        run_phase_1(args.limit_months)
    elif args.sql_only:
        run_phase_2(args.limit_files)
    elif args.dw_only:
        run_dw_pipeline()
    elif args.elastic_only:
        if run_phase_5():
            run_phase_6()
    else:
        if run_phase_1(args.limit_months) and run_phase_2(args.limit_files):
            run_dw_pipeline()

def main():
    parser = argparse.ArgumentParser(description="Orquestador ETL DIAN Colombia (Descargas + Inserción MySQL)")
    parser.add_argument("--download-only", action="store_true", help="Ejecutar únicamente la Fase 1 de descargas.")
    parser.add_argument("--sql-only", action="store_true", help="Ejecutar únicamente la Fase 2 de procesamiento SQL.")
    parser.add_argument("--dw-only", action="store_true", help="Ejecutar únicamente las Fases 3-4 (dimensiones + tabla 'importacion').")
    parser.add_argument("--elastic-only", action="store_true", help="Ejecutar únicamente las Fases 5-6 (metadata + indexación Elasticsearch).")
    parser.add_argument("--limit-months", type=int, default=None, help="Limita meses a descargar en Fase 1.")
    parser.add_argument("--limit-files", type=int, default=None, help="Limita archivos ZIP a procesar en Fase 2.")
    parser.add_argument("--loop-hours", type=float, default=None, help="Ejecutar cíclicamente como demonio en intervalos de N horas.")
    args = parser.parse_args()

    if args.loop_hours and args.loop_hours > 0:
        sleep_seconds = int(args.loop_hours * 3600)
        logger.info(f"=== Servicio ETL Colombia iniciado en modo continuo (ciclo cada {args.loop_hours} horas) ===")
        while running:
            logger.info("--- Iniciando nuevo ciclo del proceso ETL Colombia ---")
            execute_etl_flow(args)
            logger.info(f"Ciclo completado. Reposando por {args.loop_hours} horas ({sleep_seconds} segundos)...")
            
            # Dormir en incrementos cortos para responder rápido a sigterm/interrupt
            elapsed = 0
            while running and elapsed < sleep_seconds:
                time.sleep(min(5, sleep_seconds - elapsed))
                elapsed += 5
        logger.info("Servicio ETL Colombia detenido de forma limpia.")
    else:
        execute_etl_flow(args)

if __name__ == "__main__":
    main()
