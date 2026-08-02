# Modelo Dimensional — justificación detallada

## 1. Grano del hecho

Una fila = **un ítem/subpartida de una declaración de importación**. Es el
nivel de detalle que trae `temporal_impo` (varias filas pueden compartir el
mismo número de declaración cuando ésta tiene múltiples ítems).

## 2. Perfilado de cardinalidad (evidencia detrás de cada decisión)

Medido contra una muestra real de 300.000 filas de `temporal_impo` (de
2.432.390 filas totales en el momento del análisis):

| Columna(s) de origen | Distintos en la muestra | Decisión |
|---|---|---|
| `pais_origen`, `pais_procedencia`, `pais_compra`, `pais_exportador`, `bandera_transporte` | 175 / 159 / 156 / 153 / 127 | Un solo concepto (país) en 5 roles → dimensión de rol `DimPais` (ya existente, compartida) |
| `nombre_importador` / `nit_importador` | 11.824 / 11.567 | `DimImportador` (ya existente, reutilizada) |
| `nombre_exportador` | 32.980 | `DimExportador` (ya existente, reutilizada; ver nota NIT en §4) |
| `nombre_declarante` / `nit_declarante` | 1.021 / 301 | `DimAgenteAduanero` (ya existente, reutilizada) |
| `empresa_transportadora` | 567 | `DimEmpresaTransportadora` (**nueva**) |
| `subpartida_arancelaria` | 5.407 | `DimPartidas` (ya existente, reutilizada) |
| `unidad_comercial` | 10 | Texto ya limpio en el origen: se expone directo, sin dimensión |
| `forma_pago` | 12 | `DimFormaPago` (**nueva**) |
| `banc_codigo_banco` | 15 | `DimBanco` (**nueva**, sin nombre pareado en el origen) |
| `departamento_destino` / `departamento_importador` | 31 / 31 | `DimDepartamento` (**nueva**), dimensión de rol |
| `codigo_municipio` | 203 | `DimMunicipio` (**nueva**, sin nombre pareado) |
| `aduana_presentada` | 19 | `DimAduana` (ya existente, reutilizada), dimensión de rol |
| `modo_transporte` | 6 | Texto ya limpio: se expone directo (ver §5) |
| `tipo_declaracion` | 5 | `DimTipoDeclaracion` (**nueva**) |
| `clase_importador` | 4 | `DimClaseImportador` (**nueva**) |
| `tipo_importacion` | 9 | `DimTipoImportacion` (**nueva**; NO es lo mismo que `DimRegimen`, ver §6) |
| `clase_de_embalaje` | 52 | `DimEmbalaje` (**nueva**) |
| `codigo_acuerdo` | 50 | Sin nombre pareado ni catálogo confiable disponible → se expone el código crudo (ver §7) |

Degeneradas (alta cardinalidad ≈ número de declaraciones; Kimball: se dejan
sueltas en el hecho, nunca se dimensionan): `numero_formulario`,
`num_aceptacion_declaracion`, `numero_factura`, `documento_transporte`,
`manifiesto_de_carga`, y ~10 columnas más de identificación de documentos
(ver `04_Importaciones.sql`, sección "Documentos").

Sólo auditoría (sin valor analítico, excluidas de Elasticsearch, ver
[Metadata.md](Metadata.md)): `codigo_sucursal`, `codigo_cajero`,
`consecutivo_cajero`, `codigo_oficina`, `ano_registro_licencia`,
`tipo_documento1`, `usuario_dian1`, `codigo_usuario_dian1`, `activo_1`,
`activo1`, `archivo_origen`.

## 3. Deriva de esquema detectada (mismo concepto, distinto nombre de columna)

Los archivos de la DIAN cambiaron ligeramente de layout entre vigencias
(2018 vs. años más recientes). Se detectó y resolvió por `COALESCE`:

- **Agente aduanero**: `nit_declarante`/`docto_identif_declar` (NIT) y
  `nombre_declarante`/`razon_social_declarante` (nombre) — la segunda
  columna de cada par sólo tiene datos en ~0.4% de las filas (columna
  vigente en años puntuales).
- **Aduana**: `cod_aduana_presentada`/`aduana_presentada` (vigencia
  original) vs. `cod_administracion_presentada_1`/`nombre_aduana_1`
  (columnas agregadas con sufijo `_1`, vigencia nueva).
- **Departamento**: `codigo_departamento_1` (columna de deriva, sin nombre
  pareado) se suma como fuente adicional de `DimDepartamento`.

## 4. Nota de calidad de datos: `DimExportador`

`numero_identificac_export` (el campo pensado como NIT del exportador
extranjero) viene **vacío en el 100% de los registros reales** verificados
— comportamiento esperable: un exportador extranjero no está obligado a
tener NIT colombiano. `nombre_exportador` y `digito_verifi_nit_exporta` sí
están siempre poblados. Por eso la clave natural de `DimExportador` es:

```
COALESCE(NULLIF(TRIM(numero_identificac_export),''), CONCAT('NOMBRE:', UPPER(TRIM(nombre_exportador))))
```

(usar `NULL` como respaldo habría roto la deduplicación por `UNIQUE KEY`,
ya que en MySQL `NULL <> NULL`). Verificado contra la base completa:
160.725 exportadores distintos con `CodDimPais=31`.

## 5. Nota: `DimTransporte`/`DimUnidadMedida` existentes, pero no usadas para resolver `importacion`

`Dimension.DimTransporte` (9 modos de transporte) y
`Dimension.DimUnidadMedida` (19 unidades, con códigos que parecen del
esquema Eurostat: `L_ALC_100PCT`, `KG_KOH`...) ya existen, pero no hay
evidencia de que sus códigos coincidan con el esquema de códigos que usa la
DIAN (`cod_modo_transporte`, `cod_unidad_comercial`). Como el propio origen
ya trae el texto limpio y legible (`modo_transporte`, `unidad_comercial`),
`04_ETL_Importaciones.py` expone ese texto directo, sin intentar un cruce de
códigos no verificado que podría asignar el nombre incorrecto.

## 6. Nota: `tipo_importacion` no es lo mismo que `DimRegimen`

`Dimension.DimRegimen` ya existe (11 filas: "Importación definitiva/
temporal", "Reimportación", "Zona franca", "Tránsito aduanero"...). Antes de
reutilizarlo se verificaron los valores reales de `tipo_importacion` en
`temporal_impo`: "Reembolsable", "Otras no reembolsables", "Muestra
experimental", "Donación", "Muestra promocional"... — un concepto distinto
(la naturaleza/motivo del envío, no el régimen aduanero). Por eso se creó
`DimTipoImportacion` como dimensión nueva e independiente.

## 7. `DimModalidad`: clave compuesta

`moda_codigo_modalidad` (prefijo numérico: `3`, `48`, `35`...) y
`cod_modalidad_importacion` (código alfanumérico: `C100`, `C200`...) se
verificaron contra datos reales: el mismo `C100` aparece bajo distintos
prefijos (`3-C100`, `48-C100`, `35-C100`...), así que ninguna de las dos
columnas por separado identifica la modalidad — se necesitan ambas juntas.
`DimModalidad` tiene clave natural compuesta
`(CodigoModalidad, CodigoSubModalidad, CodDimPais)`. Ninguna columna del
origen trae el nombre descriptivo de la modalidad: `importacion.regimen_aduanero`
expone el código compuesto (`"48-C100"`) hasta que se enriquezca
`DimModalidad.Nombre` manualmente (la siguiente corrida del ETL empezaría a
mostrar el nombre automáticamente, sin cambios de código).

## 8. Registro "sin correspondencia"

Todas las dimensiones (nuevas y reutilizadas) tienen un registro `Id=1` con
`Nombre='NO RELACIONADO'` (misma convención que ya usaban las tablas
existentes de `Dimension`, no se inventó una nueva). `_resolver()` en
`04_ETL_Importaciones.py` cae a este comportamiento sólo quando el
diccionario no tiene el código Y no hay texto crudo de respaldo; en la
práctica, casi siempre hay texto crudo de respaldo (el propio origen trae el
nombre), así que el "sin correspondencia" real es infrecuente.
