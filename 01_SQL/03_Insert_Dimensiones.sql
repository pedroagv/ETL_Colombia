-- ============================================================================
-- 03_Insert_Dimensiones.sql
-- Trade Intelligence - Data Warehouse Comercio Exterior Colombia
-- Fase 3: seed de registros 'NO RELACIONADO' (Id=1) + patrón de referencia
-- para el poblado (bootstrap/backfill completo) de las dimensiones nuevas
-- desde `colombia.temporal_impo` hacia `Dimension`.
--
-- IMPORTANTE - relación con 02_Python/03_ETL_Dimensiones.py:
-- Este .sql es la referencia para un backfill manual completo (barre TODA
-- `temporal_impo`). La automatización real (Fase 3 en producción) la hace
-- 03_ETL_Dimensiones.py con la MISMA lógica pero acotada por
-- `archivo_origen` (un archivo a la vez, según `colombia.etl_control_carga`),
-- consultando `Dimension.*` cross-database exactamente igual que aquí
-- (MySQL permite referenciar `otra_bd.tabla` sin restricción dentro del
-- mismo servidor). Ambos son 100% idempotentes: INSERT IGNORE sobre la
-- UNIQUE KEY de la clave natural.
-- ============================================================================

-- 1) Registro NO RELACIONADO (Id=1), mismo texto/convención que ya usan las
--    tablas existentes de `Dimension` (ver DimPais.Id_DimPais=1).
INSERT IGNORE INTO `Dimension`.`DimDepartamento` (`Id_DimDepartamento`, `Codigo`, `Nombre`, `CodDimPais`) VALUES (1, '-1', 'NO RELACIONADO', 1);
INSERT IGNORE INTO `Dimension`.`DimMunicipio` (`Id_DimMunicipio`, `Codigo`, `Nombre`, `CodDimPais`) VALUES (1, '-1', 'NO RELACIONADO', 1);
INSERT IGNORE INTO `Dimension`.`DimEmpresaTransportadora` (`Id_DimEmpresaTransportadora`, `Nombre`, `CodDimPais`) VALUES (1, 'NO RELACIONADO', 1);
INSERT IGNORE INTO `Dimension`.`DimBanco` (`Id_DimBanco`, `Codigo`, `Nombre`, `CodDimPais`) VALUES (1, '-1', 'NO RELACIONADO', 1);
INSERT IGNORE INTO `Dimension`.`DimFormaPago` (`Id_DimFormaPago`, `Codigo`, `Nombre`, `CodDimPais`) VALUES (1, '-1', 'NO RELACIONADO', 1);
INSERT IGNORE INTO `Dimension`.`DimTipoDeclaracion` (`Id_DimTipoDeclaracion`, `Codigo`, `Nombre`, `CodDimPais`) VALUES (1, '-1', 'NO RELACIONADO', 1);
INSERT IGNORE INTO `Dimension`.`DimClaseImportador` (`Id_DimClaseImportador`, `Codigo`, `Nombre`, `CodDimPais`) VALUES (1, '-1', 'NO RELACIONADO', 1);
INSERT IGNORE INTO `Dimension`.`DimTipoImportacion` (`Id_DimTipoImportacion`, `Codigo`, `Nombre`, `CodDimPais`) VALUES (1, '-1', 'NO RELACIONADO', 1);
INSERT IGNORE INTO `Dimension`.`DimEmbalaje` (`Id_DimEmbalaje`, `Codigo`, `Nombre`, `CodDimPais`) VALUES (1, '-1', 'NO RELACIONADO', 1);
INSERT IGNORE INTO `Dimension`.`DimEntidadIntermedia` (`Id_DimEntidadIntermedia`, `Codigo`, `Nombre`, `CodDimPais`) VALUES (1, '-1', 'NO RELACIONADO', 1);
INSERT IGNORE INTO `Dimension`.`DimDeposito` (`Id_DimDeposito`, `Codigo`, `Nombre`, `CodDimPais`) VALUES (1, '-1', 'NO RELACIONADO', 1);
INSERT IGNORE INTO `Dimension`.`DimActividadEconomica` (`Id_DimActividadEconomica`, `Codigo`, `Nombre`, `CodDimPais`) VALUES (1, '-1', 'NO RELACIONADO', 1);
INSERT IGNORE INTO `Dimension`.`DimModalidad` (`Id_DimModalidad`, `CodigoModalidad`, `CodigoSubModalidad`, `Nombre`, `CodDimPais`) VALUES (1, '-1', '-1', 'NO RELACIONADO', 1);

-- 2) Backfill completo de referencia (CodDimPais = 31 = COLOMBIA). Patrón:
--    UNION ALL de las columnas de origen que representan el mismo concepto
--    + GROUP BY clave natural + INSERT IGNORE (set-based, sin cursores).
--    `moda_codigo_modalidad`/`cod_modalidad_importacion` sólo cubren
--    Importaciones; para Exportaciones (`temporal_expo`, aún sin cargar) el
--    mismo patrón aplica en cuanto existan datos.

INSERT IGNORE INTO `Dimension`.`DimDepartamento` (`Codigo`, `Nombre`, `CodDimPais`)
SELECT codigo_departamento, MIN(nombre_departamento), 31
FROM (
  SELECT NULLIF(TRIM(cod_departamento_destino),'') codigo_departamento, NULLIF(TRIM(departamento_destino),'') nombre_departamento FROM `colombia`.`temporal_impo`
  UNION ALL
  SELECT NULLIF(TRIM(codigo_depto_importador),''), NULLIF(TRIM(departamento_importador),'') FROM `colombia`.`temporal_impo`
) u
WHERE codigo_departamento IS NOT NULL
GROUP BY codigo_departamento;

INSERT IGNORE INTO `Dimension`.`DimMunicipio` (`Codigo`, `Nombre`, `CodDimPais`)
SELECT DISTINCT NULLIF(TRIM(codigo_municipio),''), NULL, 31
FROM `colombia`.`temporal_impo`
WHERE codigo_municipio IS NOT NULL AND TRIM(codigo_municipio) <> '';

INSERT IGNORE INTO `Dimension`.`DimEmpresaTransportadora` (`Nombre`, `CodDimPais`)
SELECT DISTINCT UPPER(TRIM(empresa_transportadora)), 31
FROM `colombia`.`temporal_impo`
WHERE empresa_transportadora IS NOT NULL AND TRIM(empresa_transportadora) <> '';

INSERT IGNORE INTO `Dimension`.`DimBanco` (`Codigo`, `Nombre`, `CodDimPais`)
SELECT DISTINCT NULLIF(TRIM(banc_codigo_banco),''), NULL, 31
FROM `colombia`.`temporal_impo`
WHERE banc_codigo_banco IS NOT NULL AND TRIM(banc_codigo_banco) <> '';

INSERT IGNORE INTO `Dimension`.`DimFormaPago` (`Codigo`, `Nombre`, `CodDimPais`)
SELECT codigo_forma_pago, MIN(nombre_forma_pago), 31
FROM (
  SELECT NULLIF(TRIM(cod_forma_pago),'') codigo_forma_pago, NULLIF(TRIM(forma_pago),'') nombre_forma_pago FROM `colombia`.`temporal_impo`
) u
WHERE codigo_forma_pago IS NOT NULL
GROUP BY codigo_forma_pago;

INSERT IGNORE INTO `Dimension`.`DimTipoDeclaracion` (`Codigo`, `Nombre`, `CodDimPais`)
SELECT codigo_tipo_declaracion, MIN(nombre_tipo_declaracion), 31
FROM (
  SELECT NULLIF(TRIM(cod_tipo_declaracion),'') codigo_tipo_declaracion, NULLIF(TRIM(tipo_declaracion),'') nombre_tipo_declaracion FROM `colombia`.`temporal_impo`
) u
WHERE codigo_tipo_declaracion IS NOT NULL
GROUP BY codigo_tipo_declaracion;

INSERT IGNORE INTO `Dimension`.`DimClaseImportador` (`Codigo`, `Nombre`, `CodDimPais`)
SELECT codigo_clase_importador, MIN(nombre_clase_importador), 31
FROM (
  SELECT NULLIF(TRIM(cod_clase_importador),'') codigo_clase_importador, NULLIF(TRIM(clase_importador),'') nombre_clase_importador FROM `colombia`.`temporal_impo`
) u
WHERE codigo_clase_importador IS NOT NULL
GROUP BY codigo_clase_importador;

INSERT IGNORE INTO `Dimension`.`DimTipoImportacion` (`Codigo`, `Nombre`, `CodDimPais`)
SELECT codigo_tipo_importacion, MIN(nombre_tipo_importacion), 31
FROM (
  SELECT NULLIF(TRIM(cod_tipo_importacion),'') codigo_tipo_importacion, NULLIF(TRIM(tipo_importacion),'') nombre_tipo_importacion FROM `colombia`.`temporal_impo`
) u
WHERE codigo_tipo_importacion IS NOT NULL
GROUP BY codigo_tipo_importacion;

INSERT IGNORE INTO `Dimension`.`DimEmbalaje` (`Codigo`, `Nombre`, `CodDimPais`)
SELECT codigo_embalaje, MIN(nombre_embalaje), 31
FROM (
  SELECT NULLIF(TRIM(codigo_embalaje),'') codigo_embalaje, NULLIF(TRIM(clase_de_embalaje),'') nombre_embalaje FROM `colombia`.`temporal_impo`
) u
WHERE codigo_embalaje IS NOT NULL
GROUP BY codigo_embalaje;

INSERT IGNORE INTO `Dimension`.`DimEntidadIntermedia` (`Codigo`, `Nombre`, `CodDimPais`)
SELECT DISTINCT NULLIF(TRIM(codigo_entidad_intermedia),''), NULL, 31
FROM `colombia`.`temporal_impo`
WHERE codigo_entidad_intermedia IS NOT NULL AND TRIM(codigo_entidad_intermedia) <> '';

INSERT IGNORE INTO `Dimension`.`DimDeposito` (`Codigo`, `Nombre`, `CodDimPais`)
SELECT DISTINCT NULLIF(TRIM(codigo_deposito),''), NULL, 31
FROM `colombia`.`temporal_impo`
WHERE codigo_deposito IS NOT NULL AND TRIM(codigo_deposito) <> '';

INSERT IGNORE INTO `Dimension`.`DimActividadEconomica` (`Codigo`, `Nombre`, `CodDimPais`)
SELECT DISTINCT NULLIF(TRIM(actividad_economica_sec),''), NULL, 31
FROM `colombia`.`temporal_impo`
WHERE actividad_economica_sec IS NOT NULL AND TRIM(actividad_economica_sec) <> '';

INSERT IGNORE INTO `Dimension`.`DimModalidad` (`CodigoModalidad`, `CodigoSubModalidad`, `Nombre`, `CodDimPais`)
SELECT codigo_modalidad, codigo_sub_modalidad, NULL, 31
FROM (
  SELECT DISTINCT
    NULLIF(TRIM(moda_codigo_modalidad),'') AS codigo_modalidad,
    NULLIF(TRIM(cod_modalidad_importacion),'') AS codigo_sub_modalidad
  FROM `colombia`.`temporal_impo`
) u
WHERE codigo_modalidad IS NOT NULL AND codigo_sub_modalidad IS NOT NULL;

-- 3) Dimensiones YA EXISTENTES en `Dimension` que Colombia reutiliza tal
--    cual (sólo se agregan los valores nuevos que aparezcan, con
--    CodDimPais = 31): DimAduana, DimImportador, DimExportador,
--    DimAgenteAduanero, DimPartidas. DimTransporte/DimMoneda/DimRegimen/
--    DimAcuerdoComercial ya están poblados de forma genérica (no varían
--    por país) y no requieren backfill.

INSERT IGNORE INTO `Dimension`.`DimAduana` (`Codigo`, `Nombre`, `CodDimPais`)
SELECT codigo_aduana, MIN(nombre_aduana), 31
FROM (
  SELECT NULLIF(TRIM(cod_aduana_presentada),'') codigo_aduana, NULLIF(TRIM(aduana_presentada),'') nombre_aduana FROM `colombia`.`temporal_impo`
  UNION ALL
  SELECT NULLIF(TRIM(cod_administracion_presentada_1),''), NULLIF(TRIM(nombre_aduana_1),'') FROM `colombia`.`temporal_impo`
  UNION ALL
  SELECT NULLIF(TRIM(cod_aduana_anterior),''), NULL FROM `colombia`.`temporal_impo`
  UNION ALL
  SELECT NULLIF(TRIM(cod_aduana_export),''), NULL FROM `colombia`.`temporal_impo`
  UNION ALL
  SELECT NULLIF(TRIM(cod_lugar_ingreso_mcia),''), NULLIF(TRIM(lugar_ingreso_mcia),'') FROM `colombia`.`temporal_impo`
) u
WHERE codigo_aduana IS NOT NULL
GROUP BY codigo_aduana;

INSERT IGNORE INTO `Dimension`.`DimImportador` (`Nit`, `Nombre`, `Direccion`, `Telefono`, `CodDimPais`)
SELECT nit_importador, MIN(nombre), MIN(direccion), MIN(telefono), 31
FROM (
  SELECT
    NULLIF(TRIM(nit_importador),'') AS nit_importador,
    NULLIF(TRIM(nombre_importador),'') AS nombre,
    direccion_importador AS direccion,
    telefono_importador AS telefono
  FROM `colombia`.`temporal_impo`
  WHERE nit_importador IS NOT NULL AND TRIM(nit_importador) <> ''
) u
GROUP BY nit_importador;

-- `numero_identificac_export` viene VACÍO en el 100% de los registros
-- reales (el exportador extranjero no tiene NIT colombiano); se usa el
-- nombre normalizado como clave natural de respaldo, igual que
-- DimEmpresaTransportadora (NULL no deduplica en una UNIQUE KEY de MySQL).
INSERT IGNORE INTO `Dimension`.`DimExportador` (`Nit`, `Nombre`, `Direccion`, `CodDimPais`)
SELECT nit_exportador, MIN(nombre), MIN(direccion), 31
FROM (
  SELECT
    COALESCE(NULLIF(TRIM(numero_identificac_export),''), CONCAT('NOMBRE:', UPPER(TRIM(nombre_exportador)))) AS nit_exportador,
    NULLIF(TRIM(nombre_exportador),'') AS nombre,
    direccion_exportador AS direccion
  FROM `colombia`.`temporal_impo`
  WHERE nombre_exportador IS NOT NULL AND TRIM(nombre_exportador) <> ''
) u
GROUP BY nit_exportador;

INSERT IGNORE INTO `Dimension`.`DimAgenteAduanero` (`Nit`, `Nombre`, `CodDimPais`)
SELECT nit_agente, MIN(nombre_agente), 31
FROM (
  SELECT
    NULLIF(TRIM(COALESCE(NULLIF(TRIM(nit_declarante),''), NULLIF(TRIM(docto_identif_declar),''))),'') AS nit_agente,
    NULLIF(TRIM(COALESCE(NULLIF(TRIM(nombre_declarante),''), NULLIF(TRIM(razon_social_declarante),''))),'') AS nombre_agente
  FROM `colombia`.`temporal_impo`
) u
WHERE nit_agente IS NOT NULL
GROUP BY nit_agente;

INSERT IGNORE INTO `Dimension`.`DimPartidas` (`HS10`, `HS2`, `HS4`, `HS6`, `HS8`, `CodDimPais`)
SELECT codigo, LEFT(codigo,2), LEFT(codigo,4), LEFT(codigo,6), LEFT(codigo,8), 31
FROM (
  SELECT DISTINCT NULLIF(TRIM(subpartida_arancelaria),'') AS codigo
  FROM `colombia`.`temporal_impo`
) u
WHERE codigo IS NOT NULL;
