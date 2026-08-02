# Elasticsearch (Fases 6-7)

## Quién genera el mapping y quién indexa

El mapping de Elasticsearch y el pipeline de indexación **ya existen en
TradeIntelligence** (`trade_data/elastic/mapping.py`,
`trade_data/indexing/pipeline.py`), generados 100% dinámicamente desde
`trade_data_campoelastic` — nunca hay un mapping escrito a mano ahí, y
tampoco lo hay en este proyecto. `02_Python/06_ETL_Elastic.py` dispara ese
pipeline (vía `manage.py run_indexing`, en subproceso), no lo duplica.

## Nombre de los índices

`trade_data/elastic/indices.py::index_name`: `{base_datos}_{tabla}_{año}`,
es decir **`colombia_importacion_2018`**, **`colombia_importacion_2019`**...
un índice por año, detectado dinámicamente vía `TablaOrigen.columna_anio`
(`fecha_declaracion`, configurada por la Fase 5). El esquema se antepone al
nombre de tabla porque `importacion` se repite en cada país del Data
Warehouse.

## Mapping: cómo se infiere el tipo Elastic

`trade_data/scanner/type_mapping.py::infer_es_type` mapea el `DATA_TYPE` de
MySQL a un tipo de Elasticsearch (ver tabla completa en
`03_Elastic/01_Mapping.json`, que es un snapshot de referencia — la
autoridad real es siempre lo que hay en vivo en `trade_data_campoelastic` +
Elasticsearch):

| Tipo SQL | Tipo Elastic |
|---|---|
| `varchar`, `char`, `enum`, `set` | `keyword` |
| `text`, `mediumtext`, `longtext` | `text` |
| `decimal`, `numeric`, `double` | `double` |
| `int`, `mediumint` | `integer` |
| `bigint` | `long` |
| `smallint` | `short` |
| `tinyint` | `byte` |
| `date`, `datetime`, `timestamp` | `date` |

`descripcion_mercancia` es la única columna `TEXT` (analizada como `text`,
full-text) del hecho: es deliberada, la única pensada para búsqueda libre en
vez de filtro/agrupación exacta.

## Qué se indexa y qué no (decisión + justificación)

**Se indexa** todo lo que llega a `importacion` (~100 columnas), salvo:

| Columna | Motivo de exclusión | Cómo se excluye |
|---|---|---|
| `archivo_origen` | Linaje/auditoría de carga, cero valor analítico | `activo=False` en `CampoElastic` (Fase 5) |
| `id` | Clave técnica interna | `visible=False` (sigue indexada por si sirve de referencia, pero oculta en la UI) |

Las columnas puramente administrativas de la DIAN (`codigo_sucursal`,
`codigo_cajero`, `tipo_documento1`, etc., ver [Metadata.md](Metadata.md)) ni
siquiera llegan a `importacion`, así que nunca llegan a Elasticsearch.

## Indexación incremental (Fase 7)

`trade_data/indexing/pipeline.py::run_indexing` usa `cursor.fetchmany(5000)`
(streaming, nunca carga todo en memoria) y `elasticsearch.helpers.bulk` (Bulk
API) con `raise_on_error=False` (los errores individuales de un lote no
abortan el resto). El `_id` del documento es la propia PK de `importacion`
(`id`, PK de una sola columna — ver Arquitectura.md §6 sobre por qué se
evitó una PK compuesta): reindexar la misma fila siempre sobrescribe el
mismo documento, nunca genera un duplicado.

Se agregó `--min-id` (pequeño cambio aditivo a TradeIntelligence, ver
Arquitectura.md §3) para no releer `importacion` completa en cada corrida:
`06_ETL_Elastic.py` guarda en `colombia.etl_checkpoint` (proceso
`elastic_importacion`) el último `id` indexado, y cada corrida sólo pide
`id > checkpoint`. Esto es lo que permite indexar cada archivo apenas se
carga, sin reprocesar el histórico.

Verificado en vivo: 50.000 filas de un archivo real indexadas en 3 índices
anuales (`colombia_importacion_2013/2017/2018` — la DIAN incluye
ocasionalmente correcciones de años anteriores dentro del archivo mensual
vigente, de ahí el 2013/2017 dentro de un archivo "de enero 2018").

## Reintentos y estadísticas

`helpers.bulk(..., raise_on_error=False)` devuelve `(éxitos, errores)`;
`run_indexing` los reporta en su resultado y `06_ETL_Elastic.py` los deja en
el log (`dian_dw_elastic.log`) junto con cuántos documentos se indexaron y
en qué índices. El checkpoint sólo avanza si el proceso completo terminó sin
excepción; un error deja el checkpoint donde estaba, así que la próxima
corrida vuelve a intentar exactamente las mismas filas (mismo patrón de
idempotencia que el resto del proyecto).

## Futuras cargas

Para indexar manualmente una tabla completa desde cero (backfill total, no
incremental): `python manage.py run_indexing colombia importacion` (sin
`--min-id`) desde el proyecto TradeIntelligence. El uso normal, sin embargo,
es siempre `06_ETL_Elastic.py` desde `ETL_Colombia`, que ya calcula el
`--min-id` correcto automáticamente.
