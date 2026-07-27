import argparse
import sys
import time
import signal
import logging
import subprocess

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
    cmd = [sys.executable, "01_fase_descarga.py"]
    if limit_months:
        cmd.extend(["--limit-months", str(limit_months)])
    res = subprocess.run(cmd)
    if res.returncode != 0:
        logger.error("Error en la ejecución de la Fase 1.")
        return False
    return True

def run_phase_2(limit_files=None):
    logger.info("Ejecutando Fase 2: Procesamiento ETL e Inserción en MySQL...")
    cmd = [sys.executable, "02_fase_sql.py"]
    if limit_files:
        cmd.extend(["--limit-files", str(limit_files)])
    res = subprocess.run(cmd)
    if res.returncode != 0:
        logger.error("Error en la ejecución de la Fase 2.")
        return False
    return True

def execute_etl_flow(args):
    if args.download_only:
        run_phase_1(args.limit_months)
    elif args.sql_only:
        run_phase_2(args.limit_files)
    else:
        if run_phase_1(args.limit_months):
            run_phase_2(args.limit_files)

def main():
    parser = argparse.ArgumentParser(description="Orquestador ETL DIAN Colombia (Descargas + Inserción MySQL)")
    parser.add_argument("--download-only", action="store_true", help="Ejecutar únicamente la Fase 1 de descargas.")
    parser.add_argument("--sql-only", action="store_true", help="Ejecutar únicamente la Fase 2 de procesamiento SQL.")
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
