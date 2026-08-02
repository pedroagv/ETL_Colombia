# ETL Colombia — Trade Intelligence Data Warehouse (DIAN Importaciones/Exportaciones)

Pipeline de 6 fases que descarga las estadísticas mensuales de comercio
exterior publicadas por la DIAN, construye un Data Warehouse dimensional en
MySQL (reutilizando dimensiones compartidas con otros países del Data
Warehouse) y deja los datos listos para búsqueda/reportes en Elasticsearch a
través de la plataforma **TradeIntelligence**.

Documentación completa (arquitectura, modelo dimensional, flujo ETL,
Elasticsearch, metadata) en **[04_Documentacion/README.md](04_Documentacion/README.md)**.

## Fases

| Fase | Script | Qué hace |
|---|---|---|
| 1 — Descarga | [02_Python/01_ETL_Descarga.py](02_Python/01_ETL_Descarga.py) | Descarga los ZIP mensuales de la DIAN desde `START_YEAR`, evitando redescargas (registro SQLite, [02_Python/database.py](02_Python/database.py)). |
| 2 — Staging | [02_Python/02_ETL_SQL.py](02_Python/02_ETL_SQL.py) | Carga los ZIP por streaming/chunks hacia `temporal_impo`/`temporal_expo` (TEXT crudo, sin transformar). **Sin cambios de lógica.** |
| 3 — Dimensiones | [02_Python/03_ETL_Dimensiones.py](02_Python/03_ETL_Dimensiones.py) | Puebla las dimensiones (base de datos compartida `Dimension`) por archivo pendiente. |
| 4 — Hechos | [02_Python/04_ETL_Importaciones.py](02_Python/04_ETL_Importaciones.py) | Resuelve en memoria (diccionarios) e inserta directo, ya plano, en `colombia.importacion`. |
| 5 — Metadata | [02_Python/05_ETL_Metadata.py](02_Python/05_ETL_Metadata.py) | Dispara la sincronización de metadata de TradeIntelligence + mejora labels/tipos. |
| 6 — Elasticsearch | [02_Python/06_ETL_Elastic.py](02_Python/06_ETL_Elastic.py) | Dispara la indexación incremental de TradeIntelligence (sólo lo nuevo). |

`main.py` orquesta todo: procesa **un archivo a la vez**, de punta a punta
(dimensiones → hechos → índice), antes de pasar al siguiente.

## Requisitos

- Python 3.12
- MySQL 8 en ejecución, con las bases `colombia` (este proyecto),
  `Dimension` (compartida) y, para las Fases 5-6, acceso a
  `trade_intelligence` (ver `TRADE_INTELLIGENCE_DIR` más abajo)
- Elasticsearch (para la Fase 6; opcional para el resto)
- Dependencias en [requirements.txt](requirements.txt): `requests`,
  `python-dotenv`, `pandas`, `openpyxl`, `pymysql`, `sqlalchemy`

## Configuración

Variables de entorno en `.env` (no versionado):

| Variable | Descripción |
|---|---|
| `START_YEAR` | Año desde el cual descargar estadísticas |
| `DB_PATH` | Ruta de la base SQLite de control de descargas |
| `IMPO_DIR` / `EXPO_DIR` | Carpetas de descarga de ZIPs |
| `PROCESADOS_IMPO_DIR` / `PROCESADOS_EXPO_DIR` | Carpetas de archivos ya procesados |
| `RUN_INTERVAL_DAYS` | Intervalo en días para el modo `--daemon` de la Fase 1 |
| `REQUESTS_TIMEOUT` | Timeout de las descargas HTTP (segundos) |
| `LOG_LEVEL` | Nivel de logging |
| `MYSQL_HOST` / `MYSQL_PORT` / `MYSQL_USER` / `MYSQL_PASSWORD` / `MYSQL_DATABASE` | Conexión a MySQL |
| `DW_CHUNK_SIZE` | Tamaño de bloque para las Fases 3-4 (default 50000) |
| `TRADE_INTELLIGENCE_DIR` / `TRADE_INTELLIGENCE_PYTHON` | Ruta y venv del proyecto TradeIntelligence, usados para disparar sus `manage.py` en las Fases 5-6 |

## Uso

```bash
# Instalar dependencias (dentro del venv)
pip install -r requirements.txt

# Bootstrap inicial de la base de datos (una sola vez; ver 01_SQL/)
mysql < 01_SQL/01_Dimensiones.sql
mysql < 01_SQL/02_Indices.sql
mysql < 01_SQL/03_Insert_Dimensiones.sql   # backfill completo (idempotente)
mysql < 01_SQL/04_Importaciones.sql
mysql < 01_SQL/05_Vistas.sql
mysql < 01_SQL/06_Procedimientos.sql

# Ciclo completo (Fases 1-6, un archivo a la vez)
python main.py

# Solo descarga / solo staging (igual que antes)
python main.py --download-only --limit-months 3
python main.py --sql-only --limit-files 10

# Solo Data Warehouse (Fases 3-4, sin descargar ni indexar)
python main.py --dw-only

# Solo metadata + indexación (Fases 5-6)
python main.py --elastic-only

# Modo demonio (ciclo completo cada N horas)
python main.py --loop-hours 24
```

## Estructura del proyecto

```
01_SQL/                  DDL y backfill de referencia (Dimension + colombia)
02_Python/                Fases 1-6 + módulos comunes (ver 02_Python/common/)
03_Elastic/               Snapshots de referencia de mapping/índices (no autoritativos)
04_Documentacion/         Documentación completa (empezar por README.md ahí)
Descargas/, Procesados/   ZIPs originales y ya procesados (Fase 1-2)
main.py                   Orquestador (loop por archivo)
```

## Servicios corriendo en WSL (Ubuntu, systemd)

| Servicio | Relevancia para este proyecto |
|---|---|
| `mysql.service` | Bases `colombia`, `Dimension`, `trade_intelligence` |
| `elasticsearch.service` | Destino final de la Fase 6 (vía TradeIntelligence) |
| `orquestador_etl_union_europea.service` | Otro ETL (países UE) que comparte la base `Dimension` — proyecto distinto |
| `nginx.service`, `ssh.service`, `cron.service` | Servicios base del sistema, no específicos de este proyecto |

El proyecto Django `TradeIntelligence` (otro repo, en
`../TradeIntelligence`) es quien consume `colombia.importacion`: ver
[04_Documentacion/Arquitectura.md](04_Documentacion/Arquitectura.md) para el
contrato de integración completo.
