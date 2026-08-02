# Metadata automática (Fase 5)

## Quién es el dueño real de `trade_data_campoelastic`

La tabla equivalente a lo que este proyecto originalmente iba a llamar
`trade_data_campoelastic` **ya existe** y **ya se mantiene sola**: vive en
`trade_intelligence` (la base de datos de TradeIntelligence, modelo Django
`CampoElastic`), y su sincronización automática (`trade_data.scanner.sync`)
ya está implementada ahí, de forma genérica para cualquier tabla física de
cualquier país registrado.

`02_Python/05_ETL_Metadata.py` **no reimplementa** ese escáner. Dispara
`manage.py scan_columns --tabla importacion --esquema colombia` en
subproceso (usando el Python/venv de TradeIntelligence, configurado en
`.env` vía `TRADE_INTELLIGENCE_DIR`/`TRADE_INTELLIGENCE_PYTHON`) y luego
aplica dos mejoras propias directamente en SQL.

## Qué detecta automáticamente el escáner de TradeIntelligence

Por cada columna de `colombia.importacion` (vía `INFORMATION_SCHEMA.
COLUMNS`), crea o actualiza un `CampoElastic` con: nombre de columna, tipo
SQL, longitud, si permite nulos, un label inicial simple, tipo Elastic
inferido (`trade_data/scanner/type_mapping.py`), grupo por defecto,
visible/filtro/agrupación en sus valores por defecto, y orden (posición
ordinal). Nunca borra: si una columna desaparece de `importacion`, su
`CampoElastic` se marca `activo=False` (no se elimina el registro).

## Qué mejora `05_ETL_Metadata.py` por encima de eso

### 1. Labels con acentos y preposiciones correctas

El label por defecto del escáner es deliberadamente simple
(`humanize_column_name`: sólo capitaliza la primera palabra —
`'pais_origen'` → `'Pais origen'`). `common/labels.py::humanize_label`
genera uno mejor (`'pais_origen'` → `'País de Origen'`,
`'valor_fob'` → `'Valor FOB'`, `'empresa_transportadora'` →
`'Empresa Transportadora'`) con tres piezas, 100% determinísticas, sin
ningún label escrito a mano:

- **Diccionario de acrónimos** (`FOB`, `CIF`, `IVA`, `NIT`, `DIAN`, `USD`...):
  se mantienen en mayúsculas y evitan que se les anteponga una preposición
  (`'valor_fob'` no se vuelve `'Valor de FOB'`).
- **Diccionario de conectores** (`fecha`, `numero`, `codigo`, `valor`,
  `documento`...): antepone `"de"` a la palabra siguiente, salvo que esa
  palabra ya sea un acrónimo o una preposición.
- **Diccionario de acentos**: repone tildes/eñes que el snake_case no trae
  (`declaracion` → `declaración`, `anio` → `año`).

### 2. Por qué no se pisa un label que un administrador ya editó

El escáner **nunca vuelve a tocar** `label`/`tipo_elastic` después de
crearlos (sólo actualiza `tipo_sql`/`longitud`/`permite_nulos` en cada
re-escaneo). Eso significa que comparar `fecha_creacion == fecha_ultima_
deteccion` para detectar "todavía no editado" **no funciona** (se comprobó
en la práctica: una columna re-escaneada automáticamente ya tiene esas dos
fechas distintas aunque nadie la haya tocado nunca).

La comprobación correcta, la que usa `_mejorar_labels()`: recalcular qué
label habría puesto el escáner por defecto (réplica mínima de
`humanize_column_name`) y comparar contra el label actual. Si coinciden,
nadie lo personalizó todavía → es seguro reemplazarlo. Si no coinciden, ya
sea un humano o una corrida anterior de este mismo script lo cambiaron →
se deja intacto.

### 3. Corrección de un `tipo_elastic` incorrecto detectado en producción

Al aplicar la comprobación anterior se detectó que `manifiesto_de_carga`
(columna `VARCHAR`) tenía `tipo_elastic='double'` desde una corrida previa
(anterior a esta sesión, `fecha_creacion` de varios días atrás) — un valor
que el escáner tampoco vuelve a corregir solo. Como esa fila también tenía
el label "tonto" sin editar, `_mejorar_labels()` la trata igual que un label
sin tocar y también recalcula `tipo_elastic` a partir del tipo SQL real
(mismo mapeo que usa TradeIntelligence: `varchar` → `keyword`), corrigiendo
el dato incorrecto sin arriesgar sobrescribir una personalización real.

### 4. Configuración de `columna_anio`

`TablaOrigen.columna_anio` (necesaria para que la Fase 6 pueda particionar
los índices de Elasticsearch por año) se configura en `'fecha_declaracion'`
automáticamente, **sólo si aún no tiene un valor** (respeta cualquier ajuste
manual posterior de un administrador).

### 5. Columnas ocultas/excluidas

- `id`: `visible=False` (sigue indexada — sirve de referencia — pero oculta
  en los selectores de la interfaz), mismo criterio que ya usa
  TradeIntelligence en sus propios datos de ejemplo.
- `archivo_origen`: `activo=False` (**excluida del índice por completo**).
  Es la única columna de linaje/auditoría que sigue viviendo en
  `importacion` (la necesita `04_ETL_Importaciones.py` para el borrado
  idempotente por archivo); no tiene ningún valor analítico para el usuario
  final y las reglas del proyecto piden explícitamente no indexar columnas
  administrativas.

## Columnas excluidas del hecho por completo (nunca llegan ni a `importacion`)

`codigo_sucursal`, `codigo_cajero`, `consecutivo_cajero`, `codigo_oficina`,
`ano_registro_licencia`, `tipo_documento1`, `usuario_dian1`,
`codigo_usuario_dian1`, `activo_1`, `activo1`: metadata interna de
procesamiento de la DIAN, sin valor de negocio. No forman parte de
`importacion` en absoluto (quedan sólo en `temporal_impo`, disponibles para
auditoría/soporte si alguna vez hicieran falta).

## Cómo se ve en la práctica (verificado contra la base real)

```
colombia.importacion: 26 nuevas, 0 reactivadas, 78 sin cambios, 94 desactivadas.
Labels mejorados en 198 columna(s) nueva(s); 1 oculta(s), 1 excluida(s) de Elasticsearch.
```

```sql
SELECT columna_original, label, tipo_elastic FROM trade_data_campoelastic
WHERE base_datos='colombia' AND tabla='importacion' LIMIT 5;
```
| columna_original | label | tipo_elastic |
|---|---|---|
| fecha_declaracion | Fecha de Declaración | date |
| nit_importador | NIT Importador | keyword |
| manifiesto_de_carga | Manifiesto de Carga | keyword |
| regimen_aduanero | Régimen Aduanero | keyword |
| aduana_exportacion | Aduana Exportación | keyword |
