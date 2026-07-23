import os
import sys
import glob
import io
import re
import math
import shutil
import zipfile
import logging
import argparse
import unicodedata
from datetime import datetime
from dotenv import load_dotenv

import pandas as pd
import pymysql

# Cargar variables de entorno desde .env
load_dotenv()

# Configuración de Rutas y Variables
IMPO_DIR = os.path.expanduser(os.getenv("IMPO_DIR", "Descargas/Importacion"))
EXPO_DIR = os.path.expanduser(os.getenv("EXPO_DIR", "Descargas/Exportacion"))
PROCESADOS_IMPO_DIR = os.path.expanduser(os.getenv("PROCESADOS_IMPO_DIR", "Procesados/Importacion"))
PROCESADOS_EXPO_DIR = os.path.expanduser(os.getenv("PROCESADOS_EXPO_DIR", "Procesados/Exportacion"))

# Configuración de MySQL
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "colombia")

LOG_LEVEL_STR = os.getenv("LOG_LEVEL", "INFO").upper()

# Configurar Logging
logging_level = getattr(logging, LOG_LEVEL_STR, logging.INFO)
logging.basicConfig(
    level=logging_level,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("dian_etl_sql.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("dian_etl_sql")


def clean_column_name(column_name: str) -> str:
    """
    Limpia y normaliza el nombre de una columna para que sea válido en MySQL.
    - Quita acentos y caracteres diacríticos.
    - Convierte a minúsculas.
    - Reemplaza espacios y caracteres especiales por guiones bajos.
    """
    if not isinstance(column_name, str):
        column_name = str(column_name)

    # Normalizar acentos
    nfkd = unicodedata.normalize('NFKD', column_name)
    cleaned = "".join([c for c in nfkd if not unicodedata.combining(c)])

    # Convertir a minúsculas
    cleaned = cleaned.lower().strip()

    # Reemplazar espacios y caracteres no alfanuméricos por '_'
    cleaned = re.sub(r'[^a-z0-9_]', '_', cleaned)

    # Reemplazar guiones bajos consecutivos por uno solo
    cleaned = re.sub(r'_+', '_', cleaned)

    # Eliminar guiones bajos al inicio o final
    cleaned = cleaned.strip('_')

    # Si empieza por un número, anteponer 'col_'
    if cleaned and cleaned[0].isdigit():
        cleaned = f"col_{cleaned}"

    # Si la columna quedó vacía
    if not cleaned:
        cleaned = "campo_desconocido"

    return cleaned


def infer_mysql_type(series: pd.Series, col_name: str = "") -> str:
    """
    Infiere el tipo de dato de MySQL correspondiente a una Serie de Pandas.
    - Cadenas/Objetos o columnas identificadoras (NITs, tipo_ident, cod, programa, etc.) -> TEXT o VARCHAR.
    - Números enteros no identificadores -> BIGINT.
    - Flotantes no identificadores -> DOUBLE.
    """
    col_lower = col_name.lower() if col_name else ""

    text_keywords = [
        "tipo", "nit", "programa", "identificac", "razon_social", "direccion", "direc",
        "subpartida", "formulario", "declaracion", "cod_", "codigo_", "oficina", "aduana",
        "modo", "modalidad", "pais", "ciudad", "departamento", "region", "transporte",
        "bandera", "embarque", "certificado", "transito", "unidades", "unidad", "serie",
        "observacion", "descripcion", "moneda", "usuario", "clase"
    ]

    if any(kw in col_lower for kw in text_keywords):
        return "TEXT"

    dtype_str = str(series.dtype).lower()

    if "int" in dtype_str:
        return "BIGINT"
    elif "float" in dtype_str:
        return "DOUBLE"
    elif "datetime" in dtype_str:
        return "DATETIME"
    elif "bool" in dtype_str:
        return "TINYINT(1)"
    else:
        non_nulls = series.dropna().astype(str)
        max_len = non_nulls.str.len().max() if not non_nulls.empty else 0
        if max_len > 255:
            return "TEXT"
        return "VARCHAR(255)"


class MySQLManager:
    def __init__(self):
        self.host = MYSQL_HOST
        self.port = MYSQL_PORT
        self.user = MYSQL_USER
        self.password = MYSQL_PASSWORD
        self.db_name = MYSQL_DATABASE
        self._ensure_database_exists()

    def get_connection(self, select_db=True):
        return pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.db_name if select_db else None,
            charset="utf8mb4",
            autocommit=False
        )

    def _ensure_database_exists(self):
        """
        Crea la base de datos si no existe en el servidor MySQL local.
        """
        try:
            conn = self.get_connection(select_db=False)
            with conn.cursor() as cursor:
                sql = f"CREATE DATABASE IF NOT EXISTS `{self.db_name}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
                cursor.execute(sql)
            conn.commit()
            conn.close()
            logger.info(f"Base de datos MySQL '{self.db_name}' verificada/creada correctamente.")
        except Exception as e:
            logger.error(f"Error al verificar/crear la base de datos '{self.db_name}': {e}")
            raise e

    def get_existing_columns(self, table_name: str) -> dict:
        """
        Retorna un diccionario con las columnas existentes en una tabla de MySQL: {col_name: col_type}.
        """
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(f"SHOW COLUMNS FROM `{table_name}`")
                rows = cursor.fetchall()
                return {row[0]: row[1].lower() for row in rows}
        except pymysql.MySQLError:
            return {}
        finally:
            conn.close()

    def sync_table_schema(self, table_name: str, df: pd.DataFrame):
        """
        Crea la tabla en MySQL si no existe, o agrega nuevas columnas / ajusta tipos de columnas
        mediante ALTER TABLE si el DataFrame incluye nuevas columnas o datos de texto en columnas numéricas.
        """
        existing_cols = self.get_existing_columns(table_name)
        conn = self.get_connection()

        try:
            with conn.cursor() as cursor:
                if not existing_cols:
                    col_definitions = ["`id` BIGINT AUTO_INCREMENT PRIMARY KEY"]
                    for col in df.columns:
                        mysql_type = infer_mysql_type(df[col], col_name=col)
                        col_definitions.append(f"`{col}` {mysql_type}")

                    create_sql = f"CREATE TABLE `{table_name}` (\n  " + ",\n  ".join(col_definitions) + "\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"
                    logger.info(f"Creando tabla '{table_name}' en MySQL...")
                    cursor.execute(create_sql)
                    conn.commit()
                else:
                    for col in df.columns:
                        inferred_type = infer_mysql_type(df[col], col_name=col)
                        if col not in existing_cols:
                            alter_sql = f"ALTER TABLE `{table_name}` ADD COLUMN `{col}` {inferred_type};"
                            logger.info(f"Agregando nueva columna '{col}' ({inferred_type}) a la tabla '{table_name}'...")
                            cursor.execute(alter_sql)
                        else:
                            curr_type = existing_cols[col]
                            is_curr_numeric = any(t in curr_type for t in ["int", "double", "float", "decimal"])
                            if is_curr_numeric and ("text" in inferred_type.lower() or "varchar" in inferred_type.lower()):
                                alter_sql = f"ALTER TABLE `{table_name}` MODIFY COLUMN `{col}` TEXT;"
                                logger.info(f"Modificando columna '{col}' de {curr_type} a TEXT en la tabla '{table_name}'...")
                                cursor.execute(alter_sql)
                            elif "varchar" in curr_type and "text" in inferred_type.lower():
                                alter_sql = f"ALTER TABLE `{table_name}` MODIFY COLUMN `{col}` TEXT;"
                                logger.info(f"Ampliando columna '{col}' de {curr_type} a TEXT en la tabla '{table_name}'...")
                                cursor.execute(alter_sql)
                    conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Error sincronizando esquema para la tabla '{table_name}': {e}")
            raise e
        finally:
            conn.close()

    def insert_dataframe(self, table_name: str, df: pd.DataFrame, batch_size=5000):
        """
        Inserta un DataFrame de Pandas en la tabla especificada en bloques (batch_size).
        Si ocurre un error de truncado en alguna columna de MySQL, amplía automáticamente la columna a TEXT y reintenta.
        """
        if df.empty:
            logger.warning(f"El DataFrame para la tabla '{table_name}' está vacío. Omitiendo inserción.")
            return 0

        columns = list(df.columns)
        quoted_cols = ", ".join([f"`{c}`" for c in columns])
        placeholders = ", ".join(["%s"] * len(columns))
        sql = f"INSERT INTO `{table_name}` ({quoted_cols}) VALUES ({placeholders})"

        df_clean = df.astype(object).where(pd.notnull(df), None)

        def clean_val(x):
            if x is None or pd.isna(x):
                return None
            if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
                return None
            return x

        data_tuples = [
            tuple(clean_val(x) for x in row)
            for row in df_clean.itertuples(index=False, name=None)
        ]

        conn = self.get_connection()
        total_inserted = 0

        try:
            with conn.cursor() as cursor:
                i = 0
                while i < len(data_tuples):
                    batch = data_tuples[i:i + batch_size]
                    try:
                        cursor.executemany(sql, batch)
                        conn.commit()
                        total_inserted += len(batch)
                        logger.debug(f"Insertados {total_inserted}/{len(data_tuples)} registros en '{table_name}'.")
                        i += batch_size
                    except pymysql.err.DataError as de:
                        conn.rollback()
                        err_msg = str(de)
                        logger.warning(f"Advertencia de inserción en '{table_name}': {err_msg}. Intentando auto-corrección de columna...")
                        match = re.search(r"column ['\"]([^'\"]+)['\"]", err_msg)
                        if match:
                            col_to_fix = match.group(1)
                            alter_sql = f"ALTER TABLE `{table_name}` MODIFY COLUMN `{col_to_fix}` TEXT;"
                            logger.info(f"Modificando columna de origen '{col_to_fix}' a TEXT en tabla '{table_name}'...")
                            cursor.execute(alter_sql)
                            conn.commit()
                            # Reintentar el lote actual
                            continue
                        else:
                            raise de

            logger.info(f"Inserción completa: {total_inserted} registros insertados en la tabla '{table_name}'.")
            return total_inserted
        except Exception as e:
            conn.rollback()
            logger.error(f"Error insertando registros en la tabla '{table_name}': {e}")
            raise e
        finally:
            conn.close()


def read_file_from_zip(zip_path: str) -> pd.DataFrame:
    """
    Descomprime en memoria el primer archivo procesable (.xlsx, .xls, .csv, .txt) dentro del ZIP y lo carga a un DataFrame.
    """
    with zipfile.ZipFile(zip_path, 'r') as z:
        file_list = z.namelist()
        valid_files = [f for f in file_list if f.lower().endswith(('.xlsx', '.xls', '.csv', '.txt')) and not f.startswith('__MACOSX')]

        if not valid_files:
            raise ValueError(f"No se encontraron archivos válidos (.xlsx, .xls, .csv, .txt) dentro de {zip_path}")

        target_file = valid_files[0]
        logger.info(f"Leyendo archivo interno '{target_file}' del ZIP '{os.path.basename(zip_path)}'...")

        with z.open(target_file) as f:
            content_bytes = f.read()

            if target_file.lower().endswith(('.xlsx', '.xls')):
                df = pd.read_excel(io.BytesIO(content_bytes))
            else:
                # Intentar lectura CSV/TXT con codificaciones estándar
                try:
                    df = pd.read_csv(io.BytesIO(content_bytes), encoding='utf-8', sep=None, engine='python')
                except Exception:
                    df = pd.read_csv(io.BytesIO(content_bytes), encoding='latin1', sep=None, engine='python')

    return df


def parse_filename_metadata(filename: str) -> tuple:
    """
    Extrae (anio, mes_nombre) a partir del nombre del archivo ZIP.
    Ejemplo: '01_Importaciones_2018_Enero.zip' -> (2018, 'Enero')
    """
    match = re.search(r'(\d{4})_([A-Za-z]+)', filename)
    if match:
        return int(match.group(1)), match.group(2)
    return None, None


def process_zip_files(file_type: str, source_dir: str, target_processed_dir: str, db_manager: MySQLManager, limit_files=None, batch_size=5000):
    """
    Procesa todos los archivos ZIP contenidos en el directorio especificado.
    """
    if not os.path.exists(source_dir):
        logger.info(f"Directorio de origen '{source_dir}' no existe. Omitiendo.")
        return

    os.makedirs(target_processed_dir, exist_ok=True)

    zip_files = sorted(glob.glob(os.path.join(source_dir, "*.zip")))
    if not zip_files:
        logger.info(f"No hay archivos ZIP pendientes en '{source_dir}'.")
        return

    if limit_files:
        zip_files = zip_files[:limit_files]

    table_name = file_type.lower()  # 'importaciones' o 'exportaciones'
    logger.info(f"Encontrados {len(zip_files)} archivos ZIP para procesar en '{source_dir}' -> Tabla MySQL: '{table_name}'.")

    for zip_path in zip_files:
        filename = os.path.basename(zip_path)
        logger.info(f"=== Iniciando procesamiento: {filename} ===")

        try:
            # 1. Leer datos del ZIP
            df = read_file_from_zip(zip_path)

            if df.empty:
                logger.warning(f"El archivo {filename} está vacío.")
                continue

            # 2. Limpieza y normalización dinámica de columnas
            df.columns = [clean_column_name(col) for col in df.columns]

            # 3. Extraer metadatos del archivo y agregar columnas de auditoría
            year, month = parse_filename_metadata(filename)
            df = df.assign(
                anio_proceso=year,
                mes_proceso=month,
                archivo_origen=filename,
                fecha_carga=datetime.now()
            )

            # 4. Sincronizar esquema de tabla en MySQL (crear o alterar tabla según columnas)
            db_manager.sync_table_schema(table_name, df)

            # 5. Insertar registros en MySQL
            rows_inserted = db_manager.insert_dataframe(table_name, df, batch_size=batch_size)

            # 6. Mover archivo a la carpeta de procesados al finalizar con éxito
            target_path = os.path.join(target_processed_dir, filename)
            if os.path.exists(target_path):
                os.remove(target_path)
            shutil.move(zip_path, target_path)
            logger.info(f"¡Éxito! Archivo {filename} procesado ({rows_inserted} filas) y movido a '{target_processed_dir}'.\n")

        except Exception as e:
            logger.error(f"Error procesando el archivo '{filename}': {e}", exc_info=True)


def main():
    parser = argparse.ArgumentParser(description="ETL Fase 2: Procesamiento dinámico de ZIPs de la DIAN e inserción en MySQL.")
    parser.add_argument("--limit-files", type=int, default=None, help="Limita la cantidad de archivos a procesar por carpeta.")
    parser.add_argument("--type", choices=["impo", "expo", "all"], default="all", help="Tipo de archivos a procesar: impo, expo o all.")
    parser.add_argument("--batch-size", type=int, default=5000, help="Tamaño de lote para la inserción masiva en MySQL.")
    args = parser.parse_args()

    logger.info("Iniciando Fase 02: ETL e Inserción en MySQL (localhost)...")
    db_manager = MySQLManager()

    if args.type in ["impo", "all"]:
        logger.info("--- Procesando Importaciones ---")
        process_zip_files(
            file_type="importaciones",
            source_dir=IMPO_DIR,
            target_processed_dir=PROCESADOS_IMPO_DIR,
            db_manager=db_manager,
            limit_files=args.limit_files,
            batch_size=args.batch_size
        )

    if args.type in ["expo", "all"]:
        logger.info("--- Procesando Exportaciones ---")
        process_zip_files(
            file_type="exportaciones",
            source_dir=EXPO_DIR,
            target_processed_dir=PROCESADOS_EXPO_DIR,
            db_manager=db_manager,
            limit_files=args.limit_files,
            batch_size=args.batch_size
        )

    logger.info("=== Fase 02 completada exitosamente ===")


if __name__ == "__main__":
    main()
