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

# --- Integración con la plataforma de consumo (TradeIntelligence) ----------
# Este proyecto (ETL_Colombia) NUNCA escribe directamente en la base de datos
# `trade_intelligence` ni importa código Django: la integración es 100%
# operativa, invocando los `manage.py` ya existentes de ese proyecto (ver
# Arquitectura.md → "Contrato de integración con TradeIntelligence"). Esto
# evita duplicar lógica (sync de metadata, mapping, indexación) que esa
# plataforma ya implementa de forma genérica para cualquier país.
TRADE_INTELLIGENCE_DIR = os.getenv("TRADE_INTELLIGENCE_DIR", "")
TRADE_INTELLIGENCE_PYTHON = os.getenv(
    "TRADE_INTELLIGENCE_PYTHON",
    os.path.join(TRADE_INTELLIGENCE_DIR, "venv", "bin", "python") if TRADE_INTELLIGENCE_DIR else "",
)
# Esquema/tabla exactos que espera el escáner de TradeIntelligence
# (TRADE_DATA_TABLE_PATTERNS="importacion,exportacion", sin comodines):
TI_ESQUEMA = MYSQL_DATABASE
TI_TABLA_IMPORTACION = "importacion"
TI_TABLA_EXPORTACION = "exportacion"

# Columna de fecha que debe configurarse como `TablaOrigen.columna_anio` en
# TradeIntelligence para poder particionar los índices de Elasticsearch por
# año (ver 05_ETL_Metadata.py).
COLUMNA_ANIO_ELASTIC = "fecha_declaracion"
