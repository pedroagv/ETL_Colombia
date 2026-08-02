-- ============================================================================
-- 06_Procedimientos.sql
-- Trade Intelligence - Data Warehouse Comercio Exterior Colombia
-- Fase 4/6: mantenimiento de particiones de `importacion`.
--
-- No existe un procedimiento de materialización (PA_Elastic_Importaciones)
-- en esta versión del proyecto: dado que las dimensiones ahora viven en
-- `Dimension` y se resuelven en Python (ver 05_Vistas.sql), no hay ningún
-- JOIN pendiente que un procedimiento deba ejecutar. `importacion` se
-- llena directamente por INSERT masivo desde
-- 02_Python/04_ETL_Importaciones.py.
-- ============================================================================

USE `colombia`;

DELIMITER $$

-- sp_agregar_particion_anual: reorganiza la partición `p_futuro` (MAXVALUE)
-- de `importacion` para separar el año indicado en su propia partición.
-- Se corre una vez al año (ver Flujo_ETL.md) o manualmente antes de que
-- empiece a llegar un año nuevo de datos.
DROP PROCEDURE IF EXISTS `sp_agregar_particion_anual`$$
CREATE PROCEDURE `sp_agregar_particion_anual` (IN p_anio INT)
BEGIN
  DECLARE v_particion VARCHAR(20);
  DECLARE v_existe INT DEFAULT 0;

  SET v_particion = CONCAT('p', p_anio);

  SELECT COUNT(*) INTO v_existe
  FROM INFORMATION_SCHEMA.PARTITIONS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'importacion' AND PARTITION_NAME = v_particion;

  IF v_existe = 0 THEN
    SET @ddl = CONCAT(
      'ALTER TABLE importacion REORGANIZE PARTITION p_futuro INTO (',
      'PARTITION ', v_particion, ' VALUES LESS THAN (', p_anio + 1, '), ',
      'PARTITION p_futuro VALUES LESS THAN MAXVALUE)'
    );
    PREPARE stmt FROM @ddl;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;
  END IF;
END$$

DELIMITER ;
