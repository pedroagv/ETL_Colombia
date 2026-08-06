import argparse
import os
import sys
import time
import signal
import logging
import subprocess
import glob

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "02_Python"))
from common import db, checkpoint  # noqa: E402  (requiere el sys.path.insert de arriba)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

logger = logging.getLogger("main_etl")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True
)



running = True
current_proc = None

def handle_signal(sig, frame):
    global running
    if not running:
        logger.info("Forzando salida inmediata por interrupción del usuario (Ctrl+C).")
        sys.exit(130)
    
    logger.info(f"Señal {sig} recibida. Deteniendo el servicio ETL...")
    running = False

    if current_proc is not None and current_proc.poll() is None:
        logger.info(f"Terminando subproceso en curso (pid={current_proc.pid})...")
        try:
            current_proc.terminate()
            current_proc.wait(timeout=1)
        except Exception:
            try:
                current_proc.kill()
            except Exception:
                pass
    sys.exit(130)

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)

def _run_subprocess(cmd):
    """Lanza cmd como subproceso registrando su referencia en current_proc
    para que handle_signal pueda cortarlo de inmediato ante SIGINT/SIGTERM."""
    global current_proc
    current_proc = subprocess.Popen(cmd)
    try:
        returncode = current_proc.wait()
    except Exception:
        if current_proc and current_proc.poll() is None:
            current_proc.kill()
        raise
    finally:
        current_proc = None
    return returncode


def run_phase_1(limit_months=None):
    logger.info("Ejecutando Fase 1: Descarga de estadísticas DIAN...")
    cmd = [sys.executable, "02_Python/01_ETL_Descarga.py"]
    if limit_months:
        cmd.extend(["--limit-months", str(limit_months)])
    if _run_subprocess(cmd) != 0:
        logger.error("Error en la ejecución de la Fase 1.")
        return False
    return True

def run_phase_2(limit_files=None):
    logger.info("Ejecutando Fase 2: Procesamiento ETL e Inserción en MySQL (tabla temporal)...")
    cmd = [sys.executable, "02_Python/02_ETL_SQL.py"]
    if limit_files:
        cmd.extend(["--limit-files", str(limit_files)])
    if _run_subprocess(cmd) != 0:
        logger.error("Error en la ejecución de la Fase 2.")
        return False
    return True

def run_phase_3(archivo=None, tabla_origen=None):
    logger.info(f"Ejecutando Fase 3: Dimensiones{f' (archivo={archivo}, tabla={tabla_origen})' if archivo else ''}...")
    cmd = [sys.executable, "02_Python/03_ETL_Dimensiones.py"]
    if archivo:
        cmd.extend(["--archivo", archivo])
    if tabla_origen:
        cmd.extend(["--tabla-origen", tabla_origen])
    if _run_subprocess(cmd) != 0:
        logger.error("Error en la ejecución de la Fase 3.")
        return False
    return True

def run_phase_4(archivo=None):
    logger.info(f"Ejecutando Fase 4: tabla 'importacion'{f' (archivo={archivo})' if archivo else ''}...")
    cmd = [sys.executable, "02_Python/04_ETL_Importaciones.py"]
    if archivo:
        cmd.extend(["--archivo", archivo])
    if _run_subprocess(cmd) != 0:
        logger.error("Error en la ejecución de la Fase 4 (Importaciones).")
        return False
    return True

def run_phase_4_expo(archivo=None):
    logger.info(f"Ejecutando Fase 4 (Exportaciones): tabla 'exportacion'{f' (archivo={archivo})' if archivo else ''}...")
    cmd = [sys.executable, "02_Python/05_ETL_Exportaciones.py"]
    if archivo:
        cmd.extend(["--archivo", archivo])
    if _run_subprocess(cmd) != 0:
        logger.error("Error en la ejecución de la Fase 4 de Exportaciones.")
        return False
    return True

def run_dw_pipeline():
    """Orquesta las Fases 3-4 ARCHIVO POR ARCHIVO (Importaciones y Exportaciones).
    Fases 4 e 5 encolan cada archivo en `cola_indexacion` para que el worker de 'indexacion'
    lo indexe en Elasticsearch de forma asíncrona."""
    logger.info("Consultando archivos pendientes en el Data Warehouse (temporal_impo / temporal_expo)...")
    conn = db.get_connection(database="colombia")
    try:
        pendientes_impo = checkpoint.archivos_pendientes(conn, "temporal_impo", "HECHOS")
        pendientes_expo = checkpoint.archivos_pendientes(conn, "temporal_expo", "HECHOS")
    finally:
        conn.close()

    total_pendientes = len(pendientes_impo) + len(pendientes_expo)
    if total_pendientes == 0:
        logger.info("No hay archivos pendientes para el Data Warehouse (Fases 3-4).")
        return

    logger.info(
        f"Archivos pendientes para el Data Warehouse: {total_pendientes} "
        f"(Importación: {len(pendientes_impo)}, Exportación: {len(pendientes_expo)})"
    )

    if pendientes_impo:
        total_impo = len(pendientes_impo)
        logger.info(f"{total_impo} archivo(s) de Importación pendiente(s): se procesan uno a uno.")
        for idx, archivo in enumerate(pendientes_impo, start=1):
            if not running:
                break
            logger.info(f"=== [Importación {idx}/{total_impo}] Procesando '{archivo}' (dimensiones -> hechos) ===")
            if run_phase_3(archivo, "temporal_impo") and running and run_phase_4(archivo):
                logger.info(
                    f"=== [Importación {idx}/{total_impo}] '{archivo}' cargado en 'importacion' y encolado "
                    f"para indexación. Faltan {total_impo - idx}. ==="
                )
            elif running:
                logger.error(f"'{archivo}' quedó incompleto; se reintentará en la próxima corrida.")

    if pendientes_expo:
        total_expo = len(pendientes_expo)
        logger.info(f"{total_expo} archivo(s) de Exportación pendiente(s): se procesan uno a uno.")
        for idx, archivo in enumerate(pendientes_expo, start=1):
            if not running:
                break
            logger.info(f"=== [Exportación {idx}/{total_expo}] Procesando '{archivo}' (dimensiones -> hechos) ===")
            if run_phase_3(archivo, "temporal_expo") and running and run_phase_4_expo(archivo):
                logger.info(
                    f"=== [Exportación {idx}/{total_expo}] '{archivo}' cargado en 'exportacion' y encolado "
                    f"para indexación. Faltan {total_expo - idx}. ==="
                )
            elif running:
                logger.error(f"'{archivo}' quedó incompleto; se reintentará en la próxima corrida.")



def execute_etl_flow(args):
    if args.download_only:
        run_phase_1(args.limit_months)
    elif args.sql_only:
        run_phase_2(args.limit_files)
    elif args.dw_only:
        run_dw_pipeline()
    else:
        if run_phase_1(args.limit_months) and running:
            # 1. Primero procesar cualquier archivo que ya estuviera pendiente en temporal_impo
            run_dw_pipeline()

            # 2. Procesamiento end-to-end archivo por archivo (Fase 2 (1 archivo) -> Fases 3/4 -> Encolado)
            impo_dir = os.path.expanduser(os.getenv("IMPO_DIR", "Descargas/Importacion"))
            expo_dir = os.path.expanduser(os.getenv("EXPO_DIR", "Descargas/Exportacion"))

            processed_count = 0
            total_files_this_run = None
            while running:
                zips_impo = glob.glob(os.path.join(impo_dir, "*.zip")) if os.path.exists(impo_dir) else []
                zips_expo = glob.glob(os.path.join(expo_dir, "*.zip")) if os.path.exists(expo_dir) else []
                pendientes_ahora = len(zips_impo) + len(zips_expo)

                if not zips_impo and not zips_expo:
                    logger.info("No hay más archivos ZIP pendientes por procesar en Descargas.")
                    break

                if total_files_this_run is None:
                    total_files_this_run = pendientes_ahora + processed_count
                    logger.info(f"Total de archivos ZIP a procesar en esta corrida: {total_files_this_run}.")

                if args.limit_files and processed_count >= args.limit_files:
                    logger.info(f"Alcanzado el límite de {args.limit_files} archivos especificado en --limit-files.")
                    break

                logger.info(
                    f"--- Procesando siguiente archivo end-to-end [{processed_count + 1}/{total_files_this_run}] "
                    f"(Staging -> DW -> Cola Indexación). Pendientes: {pendientes_ahora}. ---"
                )
                if not run_phase_2(limit_files=1) or not running:
                    logger.error("Error o interrupción durante la Fase 2 del archivo actual.")
                    break

                run_dw_pipeline()
                processed_count += 1
                logger.info(
                    f"Progreso total de esta corrida: {processed_count}/{total_files_this_run} archivos "
                    f"procesados, {total_files_this_run - processed_count} pendientes."
                )

            if total_files_this_run is not None:
                logger.info(
                    f"Resumen de la corrida: {processed_count}/{total_files_this_run} archivos ZIP procesados "
                    f"end-to-end."
                )

def main():
    parser = argparse.ArgumentParser(description="Orquestador ETL DIAN Colombia (Descargas + Inserción MySQL)")
    parser.add_argument("--download-only", action="store_true", help="Ejecutar únicamente la Fase 1 de descargas.")
    parser.add_argument("--sql-only", action="store_true", help="Ejecutar únicamente la Fase 2 de procesamiento SQL.")
    parser.add_argument("--dw-only", action="store_true", help="Ejecutar únicamente las Fases 3-4 (dimensiones + tabla 'importacion').")
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
