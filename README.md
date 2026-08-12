# 🇨🇴 ETL Colombia - Comercio Exterior (DIAN)

Sistema ETL de alta performance, streaming e incremental para la extracción, transformación y carga de los datos oficiales de comercio exterior (**Importaciones** y **Exportaciones**) de Colombia publicados por la DIAN.

Los datos procesados se estructuran en un Data Warehouse MySQL (con modelo copo de nieve / dimensional reutilizable) y se encolan automáticamente para su indexación en Elasticsearch a través del worker asíncrono.

---

## 🏗️ Arquitectura y Flujo del Sistema

```
                      +------------------------------------+
                      |       Web de la DIAN (HTTP)        |
                      +------------------------------------+
                                        |
                                        v  [Fase 1: Descarga DIAN]
                      +------------------------------------+
                      |  Carpetas Locales ZIP (Descargas)  |
                      |  - Descargas/Importacion/*.zip     |
                      |  - Descargas/Exportacion/*.zip     |
                      +------------------------------------+
                                        |
                                        v  [Fase 2: Streaming Staging]
                      +------------------------------------+
                      |         MySQL: colombia            |
                      |  - temporal_impo                   |
                      |  - temporal_expo                   |
                      +------------------------------------+
                                        |
                                        v  [Fase 3: Dimensiones Compartidas]
                      +------------------------------------+
                      |         MySQL: Dimension           |
                      |  - DimAduana, DimImportador...     |
                      |  - DimExportador, DimPartidas...   |
                      +------------------------------------+
                                        |
                                        v  [Fase 4: Hechos DW]
                      +------------------------------------+
                      |         MySQL: colombia            |
                      |  - importacion                     |
                      |  - exportacion                     |
                      |  - etl_control_carga               |
                      +------------------------------------+
                                        |
                                        v  [Encolado Asíncrono]
                      +------------------------------------+
                      |     trade_intelligence             |
                      |  - cola_indexacion                 |
                      +------------------------------------+
                                        |
                                        v  [Worker Indexación / Cron]
                      +------------------------------------+
                      |       Elasticsearch Cluster        |
                      |  - colombia_importacion_{anio}     |
                      |  - colombia_exportacion_{anio}     |
                      +------------------------------------+
```

---

## 🔄 Descripción de Fases (End-to-End Archivo por Archivo)

El pipeline está diseñado para ejecutarse **archivo por archivo** (evitando saturación de memoria RAM y garantizando resiliencia ante interrupciones):

### **Fase 1: Descarga Automática desde la DIAN (`01_ETL_Descarga.py`)**
- Inspecciona los enlaces del portal oficial de la DIAN.
- Descarga los archivos comprimidos `.zip` mensuales de **Importaciones** y **Exportaciones**.
- Guarda los archivos en `Descargas/Importacion/` y `Descargas/Exportacion/` evitando re-descargar archivos ya procesados.

### **Fase 2: Streaming a Tablas Temporales Staging (`02_ETL_SQL.py`)**
- Procesa en streaming por bloques (`chunksize=5000`) cada archivo Excel `.xlsx` contenido en el ZIP.
- Crea e inserta las filas crudas en `colombia.temporal_impo` o `colombia.temporal_expo`.
- Una vez insertado en staging, elimina el archivo ZIP local para liberar espacio (el registro de descarga en SQLite evita reprocesarlo).

### **Fase 3: Población de Dimensiones Compartidas (`03_ETL_Dimensiones.py`)**
- Extrae dinámicamente los valores únicos de cada atributo (`INSERT IGNORE ... SELECT DISTINCT`).
- Inserta en la base de datos compartida `Dimension` (utilizada por múltiples países en Trade Intelligence): `DimAduana`, `DimImportador`, `DimExportador`, `DimPartidas`, `DimDepartamento`, `DimMunicipio`, `DimFormaPago`, `DimAgenteAduanero`, etc.
- Detecta e ignora automáticamente columnas que no existan en la tabla staging de un año o mes en particular para prevenir errores.

### **Fase 4: Construcción de Hechos e Idempotencia (`04_ETL_Importaciones.py` y `05_ETL_Exportaciones.py`)**
- Transforma los datos crudos hacia las tablas definitivas `colombia.importacion` y `colombia.exportacion`.
- Resuelve códigos ISO2 de país, nombres geográficos, capítulos arancelarios y llaves dimensionales.
- Registra el éxito/error del proceso en la tabla auditora `etl_control_carga`.
- Encola una tarea con estado `PENDIENTE` en `trade_intelligence.cola_indexacion`.
- Elimina los registros del archivo procesado en la tabla temporal staging.

---

## 📊 Base de Datos y Procedimientos Almacenados

### 1. Base de Datos `colombia`
- **`temporal_impo` / `temporal_expo`**: Tablas temporales de staging con columnas crudas en texto.
- **`importacion`**: Tabla de hechos de importaciones.
- **`exportacion`**: Tabla de hechos de exportaciones.
- **`etl_control_carga`**: Registro de control e idempotencia de fases.

### 2. Base de Datos `trade_intelligence`
- **`cola_indexacion`**: Registra tareas de indexación hacia Elasticsearch:
  - `pais`: `'colombia'`
  - `tipo_intercambio`: `'IMPORTACION'` o `'EXPORTACION'`
  - `procedimiento_almacenado`: `'sp_extraer_importacion_por_archivo'` o `'sp_extraer_exportacion_por_archivo'`
  - `archivo`: Nombre del archivo ZIP procesado.
  - `estado`: `'PENDIENTE'`, `'EN_PROCESO'`, `'COMPLETADO'`, `'ERROR'`

### 3. Procedimientos Almacenados (Stored Procedures)
- `sp_extraer_importacion_por_archivo(IN p_archivo VARCHAR(255))`: Procedimiento invocado por el worker de indexación para consultar y transformar todas las filas de un archivo de importaciones hacia el índice de Elasticsearch.
- `sp_extraer_exportacion_por_archivo(IN p_archivo VARCHAR(255))`: Procedimiento invocado por el worker de indexación para consultar y transformar todas las filas de un archivo de exportaciones hacia el índice de Elasticsearch.
- `sp_agregar_particion_anual(IN p_anio INT)`: Reorganiza dinámicamente las particiones anuales en MySQL.

---

## 🚀 Guía de Ejecución

### Ejecución Automática End-to-End
Para ejecutar todas las fases de manera continua e incremental:
```bash
python main.py
```

### Ejecución por Modos Específicos
- **Solo Descarga DIAN (Fase 1)**:
  ```bash
  python main.py --download-only
  ```
- **Solo Carga Staging (Fase 2)**:
  ```bash
  python main.py --sql-only
  ```
- **Solo Data Warehouse y Encolado (Fases 3 y 4)**:
  ```bash
  python main.py --dw-only
  ```

### Opciones de Pruebas
- Procesar únicamente N archivos por corrida:
  ```bash
  python main.py --limit-files 1
  ```
