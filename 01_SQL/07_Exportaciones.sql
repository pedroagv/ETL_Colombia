-- ============================================================================
-- 07_Exportaciones.sql
-- Trade Intelligence - Data Warehouse Comercio Exterior Colombia
-- Fase 4: tabla física definitiva `exportacion` + procedimiento para indexación.
-- ============================================================================

USE `colombia`;

CREATE TABLE IF NOT EXISTS `exportacion` (
  `id`                          INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `fecha_declaracion`           DATE NULL,
  `anio`                        SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  `trimestre`                   TINYINT UNSIGNED NULL,
  `mes`                         TINYINT UNSIGNED NULL,
  `nombre_mes`                  VARCHAR(20) NULL,
  `anio_mes`                    CHAR(7) NULL,
  `pais_destino`                CHAR(2) NULL,
  `pais_destino_nombre`         VARCHAR(150) NULL,
  `region_origen`               VARCHAR(150) NULL,
  `region_procedencia`          VARCHAR(150) NULL,
  `ciudad_destinatario`         VARCHAR(150) NULL,
  `aduana_despacho`             VARCHAR(150) NULL,
  `aduana_salida`               VARCHAR(150) NULL,
  `exportador`                  VARCHAR(500) NULL,
  `nit_exportador`              VARCHAR(20) NULL,
  `destinatario`                VARCHAR(255) NULL,
  `agente_aduanero`             VARCHAR(255) NULL,
  `partida_arancelaria`         VARCHAR(10) NULL,
  `capitulo`                    VARCHAR(2) NULL,
  `capitulo_nombre`             VARCHAR(150) NULL,
  `unidad_medida`               VARCHAR(100) NULL,
  `forma_pago`                  VARCHAR(150) NULL,
  `modalidad_exportacion`       VARCHAR(150) NULL,
  `tipo_declaracion`            VARCHAR(150) NULL,
  `tipo_despacho`               VARCHAR(150) NULL,
  `clase_exportador`            VARCHAR(150) NULL,
  `modo_transporte`             VARCHAR(150) NULL,
  `nacionalidad_bandera`        VARCHAR(150) NULL,
  `moneda`                      CHAR(3) NULL,
  `cantidad`                    DECIMAL(18,4) NULL,
  `peso_bruto`                  DECIMAL(18,4) NULL,
  `peso_neto`                   DECIMAL(18,4) NULL,
  `valor_fob_usd`               DECIMAL(18,2) NULL,
  `valor_fob_pesos`             DECIMAL(18,2) NULL,
  `valor_agregado_nacional_usd` DECIMAL(18,2) NULL,
  `valor_fletes_usd`            DECIMAL(18,2) NULL,
  `valor_seguros_usd`           DECIMAL(18,2) NULL,
  `valor_otros_gastos_usd`      DECIMAL(18,2) NULL,
  `num_solicitud_auto_embarque` VARCHAR(50) NULL,
  `numero_formulario`           VARCHAR(50) NULL,
  `archivo_origen`              VARCHAR(255) NULL,
  `fecha_carga_dw`              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_exportacion_anio` (`anio`),
  KEY `idx_exportacion_fecha` (`fecha_declaracion`),
  KEY `idx_exportacion_pais_destino` (`pais_destino`),
  KEY `idx_exportacion_partida` (`partida_arancelaria`),
  KEY `idx_exportacion_exportador` (`exportador`(100)),
  KEY `idx_exportacion_archivo_origen` (`archivo_origen`(191))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

DELIMITER $$

DROP PROCEDURE IF EXISTS `sp_extraer_exportacion_por_archivo`$$
CREATE PROCEDURE `sp_extraer_exportacion_por_archivo` (IN p_archivo VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci)
BEGIN
  SELECT
    e.*,
    dp.Continente        AS continente_destino,
    dp.Subcontinente     AS subcontinente_destino,
    dp.BloqueEconomico   AS bloque_economico_destino,
    dp.Region            AS region_destino
  FROM `exportacion` AS e
  LEFT JOIN (
    SELECT ISO2, Continente, Subcontinente, BloqueEconomico, Region
    FROM (
      SELECT ISO2, Continente, Subcontinente, BloqueEconomico, Region,
             ROW_NUMBER() OVER (PARTITION BY ISO2 ORDER BY Id_DimPais) AS rn
      FROM `Dimension`.`DimPais`
      WHERE ISO2 IS NOT NULL
    ) AS x
    WHERE x.rn = 1
  ) AS dp
    ON dp.ISO2 = CONVERT(UPPER(e.pais_destino) USING utf8mb4) COLLATE utf8mb4_unicode_ci
  WHERE e.archivo_origen = p_archivo;
END$$

DELIMITER ;
