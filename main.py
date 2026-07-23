import argparse
import sys
import logging
import subprocess

logger = logging.getLogger("main_etl")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

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

def main():
    parser = argparse.ArgumentParser(description="Orquestador ETL DIAN Colombia (Descargas + Inserción MySQL)")
    parser.add_argument("--download-only", action="store_true", help="Ejecutar únicamente la Fase 1 de descargas.")
    parser.add_argument("--sql-only", action="store_true", help="Ejecutar únicamente la Fase 2 de procesamiento SQL.")
    parser.add_argument("--limit-months", type=int, default=None, help="Limita meses a descargar en Fase 1.")
    parser.add_argument("--limit-files", type=int, default=None, help="Limita archivos ZIP a procesar en Fase 2.")
    args = parser.parse_args()

    if args.download_only:
        run_phase_1(args.limit_months)
    elif args.sql-only:
        run_phase_2(args.limit_files)
    else:
        if run_phase_1(args.limit_months):
            run_phase_2(args.limit_files)

if __name__ == "__main__":
    main()
