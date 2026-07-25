import os
import sys
import argparse
import time
import datetime
import logging
import zipfile
import hashlib
import requests
from dotenv import load_dotenv
from database import DianDatabase

# Cargar variables de entorno
load_dotenv()

START_YEAR = int(os.getenv("START_YEAR", "2018"))
DB_PATH = os.getenv("DB_PATH", "dian_downloads.db")
IMPO_DIR = os.path.expanduser(os.getenv("IMPO_DIR", "Descargas Impo"))
EXPO_DIR = os.path.expanduser(os.getenv("EXPO_DIR", "Descargas Expo"))
RUN_INTERVAL_DAYS = int(os.getenv("RUN_INTERVAL_DAYS", "15"))
REQUESTS_TIMEOUT = int(os.getenv("REQUESTS_TIMEOUT", "120"))
LOG_LEVEL_STR = os.getenv("LOG_LEVEL", "INFO").upper()

# Configurar logging
logging_level = getattr(logging, LOG_LEVEL_STR, logging.INFO)
logging.basicConfig(
    level=logging_level,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("dian_downloader.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("dian_downloader")

# Crear directorios de destino si no existen
os.makedirs(IMPO_DIR, exist_ok=True)
os.makedirs(EXPO_DIR, exist_ok=True)

db = DianDatabase(DB_PATH)

MONTHS_ES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]

def calculate_sha256(file_path):
    """
    Calcula el hash SHA256 de un archivo para validar su integridad y cambios.
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def is_valid_zip(file_path):
    """
    Comprueba si un archivo es un ZIP válido y realiza una verificación CRC.
    """
    if not os.path.exists(file_path):
        return False
    if not zipfile.is_zipfile(file_path):
        return False
    try:
        with zipfile.ZipFile(file_path) as zf:
            # testzip() devuelve el nombre del primer archivo corrupto o None si está bien.
            return zf.testzip() is None
    except Exception:
        return False

def get_target_months(start_year):
    """
    Genera pares de año-mes y nombres en español desde el presente hacia atrás.
    """
    now = datetime.datetime.now()
    current_year = now.year
    current_month = now.month
    
    targets = []
    for year in range(current_year, start_year - 1, -1):
        end_month = current_month if year == current_year else 12
        for month in range(end_month, 0, -1):
            month_num_str = f"{month:02d}"
            month_name = MONTHS_ES[month - 1]
            targets.append((year, month, month_num_str, month_name))
    return targets

def download_file(url, dest_path):
    """
    Descarga un archivo con requests en modo streaming.
    Valida la integridad del archivo ZIP antes de reemplazar el destino final.
    Retorna (True, file_size) si fue exitoso, o (False, error_reason) si falló.
    """
    temp_path = dest_path + ".tmp"
    try:
        response = requests.get(url, stream=True, timeout=REQUESTS_TIMEOUT)
        
        if response.status_code == 404:
            return False, "NOT_FOUND"
        
        response.raise_for_status()
        
        with open(temp_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    
        # Verificar integridad del ZIP temporal
        if not is_valid_zip(temp_path):
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return False, "CORRUPT"
            
        # Reemplazar archivo final de forma segura
        if os.path.exists(dest_path):
            os.remove(dest_path)
        os.rename(temp_path, dest_path)
        
        file_size = os.path.getsize(dest_path)
        return True, file_size
        
    except requests.exceptions.HTTPError as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        if response.status_code == 404:
            return False, "NOT_FOUND"
        return False, f"HTTP_ERROR_{response.status_code}"
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False, str(e)

def run_download_process(limit_months=None):
    logger.info("Iniciando proceso de descarga de estadísticas DIAN...")
    
    targets = get_target_months(START_YEAR)
    if limit_months:
        targets = targets[:limit_months]
        logger.info(f"Limitando la búsqueda a los últimos {limit_months} meses.")
        
    summary = {
        "success": [],
        "skipped": [],
        "failed": [],
        "not_found": []
    }
    
    # Configuración de los tipos de descarga
    download_types = [
        {
            "key": "}",
            "cap": "Importaciones",
            "dir": IMPO_DIR,
            "url_pattern": "https://www.dian.gov.co/dian/cifras/Basesestadisticasimportaciones/{month_num}_Importaciones_{year}_{month_name}.zip"
        },
        {
            "key": "exportaciones",
            "cap": "Exportaciones",
            "dir": EXPO_DIR,
            "url_pattern": "https://www.dian.gov.co/dian/cifras/Basesestadisticasexportaciones/{month_num}_Exportaciones_{year}_{month_name}.zip"
        }
    ]
    
    for year, month, month_num, month_name in targets:
        for dt in download_types:
            url = dt["url_pattern"].format(
                month_num=month_num,
                year=year,
                month_name=month_name
            )
            filename = f"{month_num}_{dt['cap']}_{year}_{month_name}.zip"
            dest_path = os.path.join(dt["dir"], filename)
            
            # Verificar si ya se encuentra en la base de datos de descargas exitosas
            if db.is_already_downloaded(url):
                # Validamos que el archivo físico realmente exista (la integridad ya se comprobó al descargar)
                if os.path.exists(dest_path):
                    logger.debug(f"Omitido: {filename} ya descargado y verificado.")
                    summary["skipped"].append((dt["key"], year, month_name, filename))
                    continue
                else:
                    logger.warning(f"El archivo {filename} figura como descargado pero no se encuentra. Reintentando descarga...")
            
            logger.info(f"Procesando {dt['cap']} - {month_name} {year}...")
            
            success, result = download_file(url, dest_path)
            
            if success:
                file_size = result
                sha256 = calculate_sha256(dest_path)
                db.record_download(dt["key"], year, month, url, filename, "SUCCESS", file_size, sha256)
                logger.info(f"¡Éxito! Descargado: {filename} ({file_size / (1024*1024):.2f} MB)")
                summary["success"].append((dt["key"], year, month_name, filename, file_size))
            else:
                if result == "NOT_FOUND":
                    # Nota: Registramos NOT_FOUND pero en siguientes corridas reintentaremos si es el año actual o el anterior
                    db.record_download(dt["key"], year, month, url, filename, "NOT_FOUND")
                    logger.info(f"No disponible (404 Not Found) para {month_name} {year}")
                    summary["not_found"].append((dt["key"], year, month_name, filename))
                else:
                    db.record_download(dt["key"], year, month, url, filename, "FAILED")
                    logger.error(f"Error descargando {filename}: {result}")
                    summary["failed"].append((dt["key"], year, month_name, filename, result))
                    
    # Mostrar reporte consolidado
    print_summary_report(summary)

def print_summary_report(summary):
    print("\n" + "="*80)
    print("                      REPORTE DE DESCARGAS ESTADÍSTICAS DIAN")
    print("="*80)
    print(f"Descargados exitosamente en esta corrida: {len(summary['success'])}")
    for item in summary["success"]:
        print(f"  [ÉXITO] {item[0].upper()} - {item[2]} {item[1]} -> {item[3]} ({item[4]/(1024*1024):.2f} MB)")
        
    print(f"Omitidos (Ya descargados previamente): {len(summary['skipped'])}")
    if summary["skipped"]:
        # Mostramos los últimos 5 para visualización rápida
        print("  Muestra de omitidos (últimos 5):")
        for item in summary["skipped"][-5:]:
            print(f"  [OMITIDO] {item[0].upper()} - {item[2]} {item[1]} -> {item[3]}")
            
    print(f"No disponibles en la web de la DIAN (404): {len(summary['not_found'])}")
    if summary["not_found"]:
         print("  Muestra de no disponibles (últimos 5):")
         for item in summary["not_found"][-5:]:
             print(f"  [404] {item[0].upper()} - {item[2]} {item[1]}")
             
    print(f"Errores en descargas: {len(summary['failed'])}")
    for item in summary["failed"]:
        print(f"  [FALLIDO] {item[0].upper()} - {item[2]} {item[1]} -> Error: {item[4]}")
    print("="*80 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Descargador automático de bases estadísticas de la DIAN.")
    parser.add_argument("--daemon", action="store_true", help="Ejecutar como daemon en segundo plano (repite cada N días).")
    parser.add_argument("--limit-months", type=int, default=None, help="Limita el número de meses hacia atrás a procesar.")
    args = parser.parse_args()
    
    if args.daemon:
        logger.info(f"Iniciando en modo daemon. Intervalo de ejecución: {RUN_INTERVAL_DAYS} días.")
        try:
            while True:
                run_download_process(args.limit_months)
                logger.info(f"Proceso finalizado. Durmiendo por {RUN_INTERVAL_DAYS} días...")
                time.sleep(RUN_INTERVAL_DAYS * 86400)
        except KeyboardInterrupt:
            logger.info("Modo daemon detenido por el usuario.")
    else:
        run_download_process(args.limit_months)
