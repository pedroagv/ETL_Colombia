-- ============================================================================
-- 04_Importaciones.sql
-- Trade Intelligence - Data Warehouse Comercio Exterior Colombia
-- Fase 4: tabla física definitiva `importacion` (nombre exacto exigido por
-- el contrato de integración con TradeIntelligence, ver Arquitectura.md) +
-- tablas de control operativo (checkpoint/idempotencia/reanudación).
--
-- Esta es la ÚNICA tabla "de negocio" que vive en `colombia` (junto a la
-- tabla temporal de staging `temporal_impo`, ya existente). Las dimensiones
-- viven en `Dimension` (ver 01_Dimensiones.sql); esta tabla ya llega FLAT
-- (sin FKs) porque 04_ETL_Importaciones.py resuelve cada valor contra los
-- diccionarios de `Dimension` EN PYTHON, en memoria, antes del INSERT. Por
-- eso no hace falta ningún JOIN SQL para producirla (ver Arquitectura.md →
-- "Por qué no hay VW_Elastic_Importaciones con JOIN").
--
-- SIN PARTICIONAR (decisión revisada): Elasticsearch ya particiona por año
-- A NIVEL DE ÍNDICE (`colombia_importacion_2018`, `..._2019`, etc. -- ver
-- TradeIntelligence: trade_data/elastic/indices.py), que es donde de verdad
-- ocurre el análisis/consulta de negocio. Particionar TAMBIÉN en MySQL
-- exigiría que `anio` fuera parte de la PRIMARY KEY (regla de MySQL para
-- PARTITION BY), degradando la PK de `id` simple a compuesta (id, anio) --
-- lo cual le impide a TradeIntelligence detectar una PK simple para el _id
-- estable del documento en Elasticsearch (cae a un hash de toda la fila,
-- ver trade_data/indexing/pipeline.py::_find_pk_column) sin aportar
-- beneficio real, ya que nadie consulta `importacion` con SQL filtrado por
-- año. Por eso `id` queda como PK simple.
-- ============================================================================

USE `colombia`;

CREATE TABLE IF NOT EXISTS `importacion` (
  `id`                          INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `fecha_declaracion`           DATE NULL,
  `anio`                        SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  `trimestre`                   TINYINT UNSIGNED NULL,
  `mes`                         TINYINT UNSIGNED NULL,
  `nombre_mes`                  VARCHAR(20) NULL,
  `anio_mes`                    CHAR(7) NULL,
  `pais_origen`                 CHAR(2) NULL,
  `pais_origen_nombre`          VARCHAR(150) NULL,
  `pais_procedencia`            VARCHAR(150) NULL,
  `pais_compra`                 VARCHAR(150) NULL,
  `pais_exportador`             VARCHAR(150) NULL,
  `bandera_transporte`          VARCHAR(150) NULL,
  `departamento_destino`        VARCHAR(150) NULL,
  `departamento_importador`     VARCHAR(150) NULL,
  `municipio`                   VARCHAR(150) NULL,
  `aduana_presentada`           VARCHAR(150) NULL,
  `aduana_anterior`             VARCHAR(150) NULL,
  `aduana_exportacion`          VARCHAR(150) NULL,
  `importador`                  VARCHAR(255) NULL,
  `nit_importador`              VARCHAR(20) NULL,
  `exportador`                  VARCHAR(255) NULL,
  `agente_aduanero`             VARCHAR(255) NULL,
  `empresa_transportadora`      VARCHAR(255) NULL,
  `partida_arancelaria`         VARCHAR(10) NULL,
  `capitulo`                    VARCHAR(2) NULL,
  `capitulo_nombre`             VARCHAR(150) NULL,
  `unidad_medida`               VARCHAR(100) NULL,
  `forma_pago`                  VARCHAR(150) NULL,
  `banco`                       VARCHAR(150) NULL,
  `regimen_aduanero`            VARCHAR(150) NULL,
  `tipo_declaracion`            VARCHAR(150) NULL,
  `clase_importador`            VARCHAR(150) NULL,
  `tipo_importacion`            VARCHAR(150) NULL,
  `modo_transporte`             VARCHAR(150) NULL,
  `embalaje`                    VARCHAR(150) NULL,
  `acuerdo_comercial`           VARCHAR(150) NULL,
  `entidad_intermedia`          VARCHAR(150) NULL,
  `deposito`                    VARCHAR(150) NULL,
  `actividad_economica`         VARCHAR(150) NULL,
  `moneda`                      CHAR(3) NULL,
  `peso_neto`                   DECIMAL(18,4) NULL,
  `peso_bruto`                  DECIMAL(18,4) NULL,
  `cantidad`                    DECIMAL(18,4) NULL,
  `cantidad_subpartidas`        DECIMAL(18,4) NULL,
  `numero_bultos`               DECIMAL(18,4) NULL,
  `tasa_cambio`                 DECIMAL(18,6) NULL,
  `num_cuotas_o_meses`          SMALLINT UNSIGNED NULL,
  `valor_fob_usd`               DECIMAL(18,2) NULL,
  `valor_cif_usd`               DECIMAL(18,2) NULL,
  `valor_aduana_usd`            DECIMAL(18,2) NULL,
  `valor_ajuste_usd`            DECIMAL(18,2) NULL,
  `valor_fletes_usd`            DECIMAL(18,2) NULL,
  `valor_seguros_usd`           DECIMAL(18,2) NULL,
  `valor_otros_gastos_usd`      DECIMAL(18,2) NULL,
  `fletes_seguros1`             DECIMAL(18,2) NULL,
  `valor_cuota_usd`             DECIMAL(18,2) NULL,
  `porcentaje_arancel`          DECIMAL(9,4) NULL,
  `base_arancel`                DECIMAL(18,2) NULL,
  `total_liquidado_arancel`     DECIMAL(18,2) NULL,
  `total_a_pagar_arancel`       DECIMAL(18,2) NULL,
  `porcentaje_iva`              DECIMAL(9,4) NULL,
  `base_iva`                    DECIMAL(18,2) NULL,
  `total_liquidado_iva`         DECIMAL(18,2) NULL,
  `total_a_pagar_iva`           DECIMAL(18,2) NULL,
  `porcentaje_otros1`           DECIMAL(9,4) NULL,
  `base_otros1`                 DECIMAL(18,2) NULL,
  `subtotal_otros1`             DECIMAL(18,2) NULL,
  `valor_total_otros`           DECIMAL(18,2) NULL,
  `otros_pagados`               DECIMAL(18,2) NULL,
  `porcentaje_sancion`          DECIMAL(9,4) NULL,
  `base_sancion`                DECIMAL(18,2) NULL,
  `total_liquidado_sancion`     DECIMAL(18,2) NULL,
  `total_a_pagar_sancion`       DECIMAL(18,2) NULL,
  `porcentaje_salvaguardia`     DECIMAL(9,4) NULL,
  `base_salvaguardia`           DECIMAL(18,2) NULL,
  `total_liquidado_salvaguardia` DECIMAL(18,2) NULL,
  `total_a_pagar_salvaguardia`  DECIMAL(18,2) NULL,
  `porcentaje_derechos_comp`    DECIMAL(9,4) NULL,
  `base_derechos_comp`          DECIMAL(18,2) NULL,
  `total_liquidado_derechos_comp` DECIMAL(18,2) NULL,
  `total_a_pagar_derechos_comp` DECIMAL(18,2) NULL,
  `porcentaje_antidumping`      DECIMAL(9,4) NULL,
  `base_antidumping`            DECIMAL(18,2) NULL,
  `total_liquidado_antidumping` DECIMAL(18,2) NULL,
  `total_a_pagar_antidumping`   DECIMAL(18,2) NULL,
  `porcentaje_rescate`          DECIMAL(9,4) NULL,
  `base_rescate`                DECIMAL(18,2) NULL,
  `total_liquidado_rescate`     DECIMAL(18,2) NULL,
  `total_a_pagar_rescate`       DECIMAL(18,2) NULL,
  `total_item1`                 DECIMAL(18,2) NULL,
  `valor_total_arancel`         DECIMAL(18,2) NULL,
  `valor_total_iva`             DECIMAL(18,2) NULL,
  `total_liquidado`             DECIMAL(18,2) NULL,
  `pago_total`                  DECIMAL(18,2) NULL,
  `valor_pagos_anteriores`      DECIMAL(18,2) NULL,
  `numero_formulario`           VARCHAR(30) NULL,
  `num_aceptacion_declaracion`  VARCHAR(30) NULL,
  `numero_factura`              VARCHAR(50) NULL,
  `documento_transporte`        VARCHAR(50) NULL,
  `manifiesto_de_carga`         VARCHAR(50) NULL,
  `descripcion_mercancia`       TEXT NULL,
  `archivo_origen`              VARCHAR(255) NULL,
  `fecha_carga_dw`              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_importacion_anio` (`anio`),
  KEY `idx_importacion_fecha` (`fecha_declaracion`),
  KEY `idx_importacion_pais_origen` (`pais_origen`),
  KEY `idx_importacion_partida` (`partida_arancelaria`),
  KEY `idx_importacion_importador` (`importador`(100)),
  KEY `idx_importacion_archivo_origen` (`archivo_origen`(191))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Nota: `archivo_origen` se conserva en `importacion` (a diferencia del
-- diseño original de este mismo proyecto) porque es indispensable para el
-- borrado idempotente por archivo (04_ETL_Importaciones.py hace
-- `DELETE FROM importacion WHERE archivo_origen = :archivo` antes de
-- reinsertar, igual que ya hace 02_ETL_SQL.py sobre `temporal_impo`). No se
-- considera "texto repetitivo" en el sentido de Kimball porque cumple una
-- función de control, no de análisis (queda oculta para Elasticsearch, ver
-- Metadata.md).

-- ----------------------------------------------------------------------------
-- Tablas de control: checkpoint/idempotencia/reanudación (ya existentes; se
-- redeclaran aquí sólo para que este script sea auto-contenido y ejecutable
-- desde cero en un entorno nuevo).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `etl_control_carga` (
  `id`                    INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `tabla_origen`          VARCHAR(64) NOT NULL,
  `archivo_origen`        VARCHAR(255) NOT NULL,
  `fase`                  VARCHAR(30) NOT NULL,
  `estado`                VARCHAR(20) NOT NULL,
  `registros_procesados`  INT UNSIGNED NULL,
  `fecha_inicio`          DATETIME NULL,
  `fecha_fin`             DATETIME NULL,
  `tiempo_ejecucion_seg`  DECIMAL(10,2) NULL,
  `mensaje_error`         TEXT NULL,
  UNIQUE KEY `uq_etl_control_carga` (`tabla_origen`, `archivo_origen`, `fase`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `etl_checkpoint` (
  `proceso`               VARCHAR(64) NOT NULL PRIMARY KEY,
  `ultimo_id_procesado`   BIGINT UNSIGNED NOT NULL DEFAULT 0,
  `registros_totales`     BIGINT UNSIGNED NOT NULL DEFAULT 0,
  `fecha_actualizacion`   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT IGNORE INTO `etl_checkpoint` (`proceso`, `ultimo_id_procesado`) VALUES ('elastic_importacion', 0);
