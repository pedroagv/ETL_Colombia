"""Configuración compartida por las Fases 3-4 (Trade Intelligence DW Colombia).

Sigue el mismo patrón que 02_fase_sql.py: variables de entorno desde `.env`
en la raíz del proyecto, con valores por defecto sensatos. No introduce un
sistema de configuración nuevo/paralelo.
"""
import os
from dotenv import load_dotenv

# Se carga desde la raíz del repo (mismo .env que usan 01_fase_descarga.py y
# 02_fase_sql.py), sin importar desde qué directorio se invoque el script.
_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(_ROOT_DIR, ".env"))

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "colombia")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Tamaño de bloque por defecto para todo procesamiento por chunks en las
# Fases 3-4 (perfilado, población de dimensiones, carga de hechos). Se puede
# sobrescribir por script vía --batch-size.
DEFAULT_CHUNK_SIZE = int(os.getenv("DW_CHUNK_SIZE", "50000"))
