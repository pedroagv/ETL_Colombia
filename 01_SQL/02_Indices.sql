-- ============================================================================
-- 02_Indices.sql
-- Trade Intelligence - Data Warehouse Comercio Exterior Colombia
-- Fase 3: índices secundarios sobre las dimensiones nuevas (Dimension) y
-- sobre la tabla física final (colombia.importacion).
--
-- Las claves naturales ya quedaron como UNIQUE KEY en 01_Dimensiones.sql
-- (son las que usa Python para resolver el diccionario en memoria). Aquí
-- sólo se agregan índices de apoyo para búsqueda/orden por nombre.
-- ============================================================================

USE `Dimension`;

DELIMITER $$

DROP PROCEDURE IF EXISTS `sp_crear_indice_si_no_existe`$$
CREATE PROCEDURE `sp_crear_indice_si_no_existe` (
  IN p_schema      VARCHAR(64),
  IN p_tabla       VARCHAR(64),
  IN p_indice      VARCHAR(64),
  IN p_definicion  VARCHAR(512)
)
BEGIN
  DECLARE v_existe INT DEFAULT 0;

  SELECT COUNT(*) INTO v_existe
  FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = p_schema AND TABLE_NAME = p_tabla AND INDEX_NAME = p_indice;

  IF v_existe = 0 THEN
    SET @ddl = CONCAT('CREATE INDEX `', p_indice, '` ON `', p_schema, '`.`', p_tabla, '` ', p_definicion);
    PREPARE stmt FROM @ddl;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;
  END IF;
END$$

DELIMITER ;

CALL sp_crear_indice_si_no_existe('Dimension', 'DimDepartamento', 'idx_dimdepartamento_nombre', '(`Nombre`)');
CALL sp_crear_indice_si_no_existe('Dimension', 'DimMunicipio', 'idx_dimmunicipio_nombre', '(`Nombre`)');
CALL sp_crear_indice_si_no_existe('Dimension', 'DimEmpresaTransportadora', 'idx_dimtransportadora_pais', '(`CodDimPais`)');
CALL sp_crear_indice_si_no_existe('Dimension', 'DimModalidad', 'idx_dimmodalidad_pais', '(`CodDimPais`)');

DROP PROCEDURE IF EXISTS `sp_crear_indice_si_no_existe`;

-- Índices de la tabla final (se crean también en 04_Importaciones.sql como
-- parte de su DDL; este bloque queda por si `importacion` ya existía antes
-- de aplicar este proyecto y sólo hace falta agregar índices).
USE `colombia`;

DELIMITER $$
DROP PROCEDURE IF EXISTS `sp_crear_indice_si_no_existe`$$
CREATE PROCEDURE `sp_crear_indice_si_no_existe` (
  IN p_tabla       VARCHAR(64),
  IN p_indice      VARCHAR(64),
  IN p_definicion  VARCHAR(512)
)
BEGIN
  DECLARE v_existe INT DEFAULT 0;
  SELECT COUNT(*) INTO v_existe
  FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = p_tabla AND INDEX_NAME = p_indice;
  IF v_existe = 0 THEN
    SET @ddl = CONCAT('CREATE INDEX `', p_indice, '` ON `', p_tabla, '` ', p_definicion);
    PREPARE stmt FROM @ddl;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;
  END IF;
END$$
DELIMITER ;

CALL sp_crear_indice_si_no_existe('importacion', 'idx_importacion_fecha', '(`fecha_declaracion`)');
CALL sp_crear_indice_si_no_existe('importacion', 'idx_importacion_pais_origen', '(`pais_origen`)');
CALL sp_crear_indice_si_no_existe('importacion', 'idx_importacion_partida', '(`partida_arancelaria`)');
CALL sp_crear_indice_si_no_existe('importacion', 'idx_importacion_importador', '(`importador`(100))');

DROP PROCEDURE IF EXISTS `sp_crear_indice_si_no_existe`;
