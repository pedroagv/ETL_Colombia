# ETL Colombia — DIAN Importaciones/Exportaciones

Proceso ETL en dos fases que descarga las estadísticas mensuales de importaciones y exportaciones publicadas por la DIAN, y las procesa e inserta en una base de datos MySQL.

## Fases

- **Fase 1 — Descarga** ([01_fase_descarga.py](01_fase_descarga.py)): descarga los ZIP mensuales de la DIAN desde `START_YEAR` hasta la fecha, evitando redescargas mediante un registro en SQLite ([database.py](database.py)). Soporta modo `--daemon` para repetirse cada `RUN_INTERVAL_DAYS`.
- **Fase 2 — Procesamiento SQL** ([02_fase_sql.py](02_fase_sql.py)): procesa dinámicamente los ZIP descargados (Excel/CSV), crea las tablas necesarias (`temporal_impo` y `temporal_expo`) en MySQL e inserta los datos por lotes.
- **Orquestador** ([main.py](main.py)): ejecuta ambas fases en orden, o cada una por separado.

## Requisitos

- Python 3.12
- MySQL en ejecución (ver `MYSQL_*` en `.env`)
- Dependencias en [requirements.txt](requirements.txt): `requests`, `python-dotenv`, `pandas`, `openpyxl`, `pymysql`, `sqlalchemy`

## Configuración

Variables de entorno en `.env` (no versionado):

| Variable | Descripción |
|---|---|
| `START_YEAR` | Año desde el cual descargar estadísticas |
| `DB_PATH` | Ruta de la base SQLite de control de descargas |
| `IMPO_DIR` / `EXPO_DIR` | Carpetas de descarga de ZIPs |
| `PROCESADOS_IMPO_DIR` / `PROCESADOS_EXPO_DIR` | Carpetas de archivos ya procesados |
| `RUN_INTERVAL_DAYS` | Intervalo en días para el modo `--daemon` |
| `REQUESTS_TIMEOUT` | Timeout de las descargas HTTP (segundos) |
| `LOG_LEVEL` | Nivel de logging |
| `MYSQL_HOST` / `MYSQL_PORT` / `MYSQL_USER` / `MYSQL_PASSWORD` / `MYSQL_DATABASE` | Conexión a MySQL |

## Uso

```bash
# Instalar dependencias (dentro del venv)
pip install -r requirements.txt

# Ejecutar ambas fases
python main.py

# Solo descarga (con límite opcional de meses)
python main.py --download-only --limit-months 3

# Solo procesamiento SQL (con límite opcional de archivos)
python main.py --sql-only --limit-files 10
```

## Estructura de datos

- `Descargas/Importacion` y `Descargas/Exportacion`: ZIPs originales descargados de la DIAN.
- `Procesados/Importacion` y `Procesados/Exportacion`: archivos ya procesados por la Fase 2.
- `dian_downloads.db`: registro SQLite de descargas (evita duplicados).
- `dian_downloader.log` / `dian_etl_sql.log`: logs de cada fase.

## Servicios corriendo en WSL (Ubuntu, systemd)

Detectados en el entorno WSL donde vive este proyecto (`systemctl list-units --type=service --state=running`):

| Servicio | Estado | Relevancia para este proyecto |
|---|---|---|
| `mysql.service` | activo (puerto `3306`) | Base de datos destino de la Fase 2 (`MYSQL_HOST=localhost`) |
| `elasticsearch.service` | activo (puertos `9200`/`9300`) | No usado por este proyecto |
| `nginx.service` | activo | No usado por este proyecto |
| `orquestador_etl_union_europea.service` | activo | Otro ETL (Eurostat, fases 3-7, cíclico) — proyecto distinto, no relacionado a este repo |
| `ssh.service` | activo (puerto `22`) | Acceso remoto SSH |
| `cron.service` | activo | Demonio de tareas programadas |
| `unattended-upgrades.service` | activo | Actualizaciones automáticas del sistema |
| `systemd-*`, `dbus`, `polkit`, `rsyslog`, `getty@tty1` | activos | Servicios base del sistema |

Adicionalmente hay un proceso Django (`manage.py runserver`) escuchando en `127.0.0.1:8000`, correspondiente al proyecto `TradeIntelligence` (no a este repo).

> Nota: **solo `mysql.service` es directamente relevante** para este proyecto, ya que la Fase 2 inserta los datos ahí. El resto son servicios del sistema o de otros proyectos presentes en la misma máquina WSL.
