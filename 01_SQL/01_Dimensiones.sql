-- ============================================================================
-- 01_Dimensiones.sql
-- Trade Intelligence - Data Warehouse Comercio Exterior Colombia
-- Fase 3: dimensiones NUEVAS que se agregan a la base de datos compartida
-- `Dimension` (ya existente, usada también por el ETL de países de la UE).
--
-- DECISIÓN DE ARQUITECTURA (corrige el diseño inicial de este mismo
-- proyecto, ver Arquitectura.md → "Historial de decisiones"): las
-- dimensiones NO viven en `colombia`. Viven en `Dimension`, una única vez,
-- compartidas entre todos los países del Data Warehouse. `colombia` sólo
-- contiene la tabla temporal de staging y la tabla física final
-- (`importacion`/`exportacion`); ninguna dimensión física local.
--
-- Reutilización confirmada contra la base real (no se recrean):
--   DimPais (id 31 = COLOMBIA), DimAduana, DimPuerto, DimImportador,
--   DimExportador, DimAgenteAduanero, DimPartidas, DimUnidadMedida,
--   DimTransporte (modo de transporte), DimMoneda, DimIncoterm, DimRegimen,
--   DimAcuerdoComercial, DimTiempo.
-- NO se usan las tablas legacy DimPartida/DimUnidad (su columna `codpais`
-- no corresponde a `DimPais.Id_DimPais`, son de otro esquema de país propio
-- del ETL de la Unión Europea; usarlas arriesgaría cruzar datos entre
-- países. Ver conversación de diseño).
--
-- Dimensiones NUEVAS (no existían, se detectaron por cardinalidad/reutili-
-- zación real sobre `temporal_impo`, ver Modelo_Dimensional.md): se agregan
-- siguiendo EXACTAMENTE la misma convención de las tablas nuevas ya
-- existentes (`Id_DimX` autoincremental, `CodDimPais` con FOREIGN KEY real
-- hacia `DimPais`, collation utf8mb4_unicode_ci) para que cualquier otro
-- país del Data Warehouse pueda reutilizarlas a futuro.
--
-- Cada dimensión tiene un registro Id=1 'NO RELACIONADO' (mismo texto que
-- ya usan las tablas existentes, ver DimPais.Id_DimPais=1) para resolver
-- automáticamente valores de origen vacíos o sin correspondencia.
-- ============================================================================

USE `Dimension`;

CREATE TABLE IF NOT EXISTS `DimDepartamento` (
  `Id_DimDepartamento` SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `Codigo`             VARCHAR(10) NOT NULL,
  `Nombre`             VARCHAR(150) NOT NULL,
  `CodDimPais`         INT NOT NULL DEFAULT 1,
  PRIMARY KEY (`Id_DimDepartamento`),
  UNIQUE KEY `UQ_DimDepartamento_Codigo_Pais` (`Codigo`, `CodDimPais`),
  KEY `FK_DimDepartamento_Pais` (`CodDimPais`),
  CONSTRAINT `FK_DimDepartamento_Pais` FOREIGN KEY (`CodDimPais`) REFERENCES `DimPais` (`Id_DimPais`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `DimMunicipio` (
  `Id_DimMunicipio`       INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `Codigo`                VARCHAR(10) NOT NULL,
  `Nombre`                VARCHAR(150) NULL,
  `CodDimDepartamento`    SMALLINT UNSIGNED NULL,
  `CodDimPais`            INT NOT NULL DEFAULT 1,
  PRIMARY KEY (`Id_DimMunicipio`),
  UNIQUE KEY `UQ_DimMunicipio_Codigo_Pais` (`Codigo`, `CodDimPais`),
  KEY `FK_DimMunicipio_Pais` (`CodDimPais`),
  KEY `FK_DimMunicipio_Departamento` (`CodDimDepartamento`),
  CONSTRAINT `FK_DimMunicipio_Pais` FOREIGN KEY (`CodDimPais`) REFERENCES `DimPais` (`Id_DimPais`)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `FK_DimMunicipio_Departamento` FOREIGN KEY (`CodDimDepartamento`) REFERENCES `DimDepartamento` (`Id_DimDepartamento`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Sin código propio en el origen (ver 02_ETL_SQL.py): la clave natural es el
-- propio nombre normalizado (TRIM+UPPER) por país.
CREATE TABLE IF NOT EXISTS `DimEmpresaTransportadora` (
  `Id_DimEmpresaTransportadora` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `Nombre`                      VARCHAR(255) NOT NULL,
  `CodDimPais`                  INT NOT NULL DEFAULT 1,
  PRIMARY KEY (`Id_DimEmpresaTransportadora`),
  UNIQUE KEY `UQ_DimEmpresaTransportadora_Nombre_Pais` (`Nombre`, `CodDimPais`),
  KEY `FK_DimEmpresaTransportadora_Pais` (`CodDimPais`),
  CONSTRAINT `FK_DimEmpresaTransportadora_Pais` FOREIGN KEY (`CodDimPais`) REFERENCES `DimPais` (`Id_DimPais`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `DimBanco` (
  `Id_DimBanco` SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `Codigo`      VARCHAR(10) NOT NULL,
  `Nombre`      VARCHAR(150) NULL,
  `CodDimPais`  INT NOT NULL DEFAULT 1,
  PRIMARY KEY (`Id_DimBanco`),
  UNIQUE KEY `UQ_DimBanco_Codigo_Pais` (`Codigo`, `CodDimPais`),
  KEY `FK_DimBanco_Pais` (`CodDimPais`),
  CONSTRAINT `FK_DimBanco_Pais` FOREIGN KEY (`CodDimPais`) REFERENCES `DimPais` (`Id_DimPais`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `DimFormaPago` (
  `Id_DimFormaPago` SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `Codigo`          VARCHAR(10) NOT NULL,
  `Nombre`          VARCHAR(150) NULL,
  `CodDimPais`      INT NOT NULL DEFAULT 1,
  PRIMARY KEY (`Id_DimFormaPago`),
  UNIQUE KEY `UQ_DimFormaPago_Codigo_Pais` (`Codigo`, `CodDimPais`),
  KEY `FK_DimFormaPago_Pais` (`CodDimPais`),
  CONSTRAINT `FK_DimFormaPago_Pais` FOREIGN KEY (`CodDimPais`) REFERENCES `DimPais` (`Id_DimPais`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `DimTipoDeclaracion` (
  `Id_DimTipoDeclaracion` SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `Codigo`                VARCHAR(10) NOT NULL,
  `Nombre`                VARCHAR(150) NULL,
  `CodDimPais`            INT NOT NULL DEFAULT 1,
  PRIMARY KEY (`Id_DimTipoDeclaracion`),
  UNIQUE KEY `UQ_DimTipoDeclaracion_Codigo_Pais` (`Codigo`, `CodDimPais`),
  KEY `FK_DimTipoDeclaracion_Pais` (`CodDimPais`),
  CONSTRAINT `FK_DimTipoDeclaracion_Pais` FOREIGN KEY (`CodDimPais`) REFERENCES `DimPais` (`Id_DimPais`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `DimClaseImportador` (
  `Id_DimClaseImportador` SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `Codigo`                VARCHAR(10) NOT NULL,
  `Nombre`                VARCHAR(150) NULL,
  `CodDimPais`            INT NOT NULL DEFAULT 1,
  PRIMARY KEY (`Id_DimClaseImportador`),
  UNIQUE KEY `UQ_DimClaseImportador_Codigo_Pais` (`Codigo`, `CodDimPais`),
  KEY `FK_DimClaseImportador_Pais` (`CodDimPais`),
  CONSTRAINT `FK_DimClaseImportador_Pais` FOREIGN KEY (`CodDimPais`) REFERENCES `DimPais` (`Id_DimPais`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Confirmado contra datos reales (ver conversación de diseño): NO es lo
-- mismo que DimRegimen (que ya existe: "Importación definitiva/temporal",
-- "Reimportación", "Zona franca"...). `tipo_importacion` en la DIAN
-- describe el motivo/naturaleza del envío ("Reembolsable", "Donación",
-- "Muestra experimental"...), un concepto distinto.
CREATE TABLE IF NOT EXISTS `DimTipoImportacion` (
  `Id_DimTipoImportacion` SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `Codigo`                VARCHAR(10) NOT NULL,
  `Nombre`                VARCHAR(150) NULL,
  `CodDimPais`            INT NOT NULL DEFAULT 1,
  PRIMARY KEY (`Id_DimTipoImportacion`),
  UNIQUE KEY `UQ_DimTipoImportacion_Codigo_Pais` (`Codigo`, `CodDimPais`),
  KEY `FK_DimTipoImportacion_Pais` (`CodDimPais`),
  CONSTRAINT `FK_DimTipoImportacion_Pais` FOREIGN KEY (`CodDimPais`) REFERENCES `DimPais` (`Id_DimPais`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `DimEmbalaje` (
  `Id_DimEmbalaje` SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `Codigo`         VARCHAR(10) NOT NULL,
  `Nombre`         VARCHAR(150) NULL,
  `CodDimPais`     INT NOT NULL DEFAULT 1,
  PRIMARY KEY (`Id_DimEmbalaje`),
  UNIQUE KEY `UQ_DimEmbalaje_Codigo_Pais` (`Codigo`, `CodDimPais`),
  KEY `FK_DimEmbalaje_Pais` (`CodDimPais`),
  CONSTRAINT `FK_DimEmbalaje_Pais` FOREIGN KEY (`CodDimPais`) REFERENCES `DimPais` (`Id_DimPais`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `DimEntidadIntermedia` (
  `Id_DimEntidadIntermedia` SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `Codigo`                  VARCHAR(10) NOT NULL,
  `Nombre`                  VARCHAR(150) NULL,
  `CodDimPais`              INT NOT NULL DEFAULT 1,
  PRIMARY KEY (`Id_DimEntidadIntermedia`),
  UNIQUE KEY `UQ_DimEntidadIntermedia_Codigo_Pais` (`Codigo`, `CodDimPais`),
  KEY `FK_DimEntidadIntermedia_Pais` (`CodDimPais`),
  CONSTRAINT `FK_DimEntidadIntermedia_Pais` FOREIGN KEY (`CodDimPais`) REFERENCES `DimPais` (`Id_DimPais`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `DimDeposito` (
  `Id_DimDeposito` SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `Codigo`         VARCHAR(10) NOT NULL,
  `Nombre`         VARCHAR(150) NULL,
  `CodDimPais`     INT NOT NULL DEFAULT 1,
  PRIMARY KEY (`Id_DimDeposito`),
  UNIQUE KEY `UQ_DimDeposito_Codigo_Pais` (`Codigo`, `CodDimPais`),
  KEY `FK_DimDeposito_Pais` (`CodDimPais`),
  CONSTRAINT `FK_DimDeposito_Pais` FOREIGN KEY (`CodDimPais`) REFERENCES `DimPais` (`Id_DimPais`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `DimActividadEconomica` (
  `Id_DimActividadEconomica` SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `Codigo`                   VARCHAR(10) NOT NULL,
  `Nombre`                   VARCHAR(150) NULL,
  `CodDimPais`               INT NOT NULL DEFAULT 1,
  PRIMARY KEY (`Id_DimActividadEconomica`),
  UNIQUE KEY `UQ_DimActividadEconomica_Codigo_Pais` (`Codigo`, `CodDimPais`),
  KEY `FK_DimActividadEconomica_Pais` (`CodDimPais`),
  CONSTRAINT `FK_DimActividadEconomica_Pais` FOREIGN KEY (`CodDimPais`) REFERENCES `DimPais` (`Id_DimPais`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Clave compuesta confirmada contra datos reales: `moda_codigo_modalidad`
-- (prefijo, ej. '3','48','35') + `cod_modalidad_importacion` (ej. 'C100',
-- 'C200') identifican juntos la modalidad; ninguna de las dos por separado
-- alcanza (un mismo 'C100' aparece bajo distintos prefijos).
CREATE TABLE IF NOT EXISTS `DimModalidad` (
  `Id_DimModalidad`     INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `CodigoModalidad`     VARCHAR(10) NOT NULL,
  `CodigoSubModalidad`  VARCHAR(10) NOT NULL,
  `Nombre`              VARCHAR(150) NULL,
  `CodDimPais`          INT NOT NULL DEFAULT 1,
  PRIMARY KEY (`Id_DimModalidad`),
  UNIQUE KEY `UQ_DimModalidad_Codigo_Pais` (`CodigoModalidad`, `CodigoSubModalidad`, `CodDimPais`),
  KEY `FK_DimModalidad_Pais` (`CodDimPais`),
  CONSTRAINT `FK_DimModalidad_Pais` FOREIGN KEY (`CodDimPais`) REFERENCES `DimPais` (`Id_DimPais`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
