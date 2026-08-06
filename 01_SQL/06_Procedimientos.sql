-- ============================================================================
-- 06_Procedimientos.sql
-- Trade Intelligence - Data Warehouse Comercio Exterior Colombia
-- Fase 4/6: mantenimiento de particiones de `importacion`, y el
-- procedimiento que consume el proyecto 'indexacion' para extraer los
-- datos de un archivo recién cargado (contrato de la cola de indexación,
-- ver proyectos/indexacion/README.md).
--
-- `importacion` ya llega FLAT (sin FKs, ver 04_Importaciones.sql): las
-- dimensiones se resuelven en Python al insertar, así que
-- sp_extraer_importacion_por_archivo NO necesita reconstruir ningún JOIN de
-- negocio — solo filtra por archivo y enriquece con Continente/Subcontinente
-- (que `importacion` no trae) uniendo `Dimension`.`DimPais` por ISO2.
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

-- sp_extraer_importacion_por_archivo: lo que dispara 'indexacion' cuando la
-- cola le avisa que `p_archivo` terminó de cargarse en `importacion`.
-- Devuelve exactamente esas filas, listas para indexar (ya planas, más
-- continente/subcontinente/bloque económico del país de origen, que
-- `importacion` no trae por su cuenta).
DROP PROCEDURE IF EXISTS `sp_extraer_importacion_por_archivo`$$
-- COLLATE explícito en el parámetro: la base `colombia` tiene collation por
-- defecto utf8mb4_unicode_ci, pero `importacion.archivo_origen` se creó en
-- utf8mb4_0900_ai_ci (default de MySQL 8 a nivel de tabla) — sin fijar la
-- collation del parámetro, MySQL lo resuelve contra la de la base y el
-- WHERE siguiente falla con "Illegal mix of collations".
CREATE PROCEDURE `sp_extraer_importacion_por_archivo` (IN p_archivo VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci)
BEGIN
  -- `Dimension.DimPais.ISO2` NO es único (hay países duplicados: HK, SX, TF,
  -- PS, CS) — un JOIN directo por ISO2 fanea filas de `importacion` para
  -- esos países (mismo `id` aparece más de una vez en el resultado, pisando
  -- documentos en Elasticsearch en vez de indexar 1:1). Este subquery se
  -- queda con un solo DimPais por ISO2 (el de menor Id_DimPais) para que el
  -- JOIN externo sea siempre 1:1 con `importacion`, sin importar duplicados
  -- en la dimensión.
  SELECT
    i.*,
    dp.Continente        AS continente_origen,
    dp.Subcontinente     AS subcontinente_origen,
    dp.BloqueEconomico   AS bloque_economico_origen,
    dp.Region            AS region_origen
  FROM `importacion` AS i
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
    -- `Dimension` está en utf8mb4_unicode_ci y `colombia` en la collation
    -- por defecto de MySQL 8 (utf8mb4_0900_ai_ci) — sin este COLLATE
    -- explícito, el JOIN falla con "Illegal mix of collations".
    ON dp.ISO2 = CONVERT(UPPER(i.pais_origen) USING utf8mb4) COLLATE utf8mb4_unicode_ci
  WHERE i.archivo_origen = p_archivo;
END$$

-- sp_extraer_exportacion_por_archivo: lo que dispara 'indexacion' cuando la
-- cola le avisa que `p_archivo` terminó de cargarse en `exportacion`.
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

