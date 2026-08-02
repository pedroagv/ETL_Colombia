-- ============================================================================
-- 05_Vistas.sql
-- Trade Intelligence - Data Warehouse Comercio Exterior Colombia
-- Fase 4: capa de salida lógica hacia Elasticsearch.
--
-- DECISIÓN DE ARQUITECTURA (actualizada tras confirmar el modelo de
-- dimensiones compartidas en `Dimension`, ver Arquitectura.md → "Historial
-- de decisiones"):
--
-- El diseño original de este archivo definía VW_Elastic_Importaciones como
-- una vista con ~20 JOIN hacia dimensiones locales. ESO YA NO APLICA: las
-- dimensiones viven en `Dimension` (compartidas entre países) y la
-- resolución de cada valor sucede EN PYTHON, en memoria, contra
-- diccionarios cargados una única vez (ver 02_Python/04_ETL_Importaciones.py)
-- -- exactamente como exige la arquitectura ("nunca hacer JOIN repetitivos
-- durante el ETL"). Por lo tanto `colombia.importacion` ya nace flat, sin
-- ningún FK que resolver.
--
-- Como el escáner de metadatos de TradeIntelligence (la plataforma que
-- consume estos datos) sólo reconoce TABLAS FÍSICAS (TABLE_TYPE='BASE
-- TABLE') con nombre exacto 'importacion'/'exportacion', esa tabla física
-- ES la capa de salida real. Esta vista es sólo un ALIAS de nombre estable
-- (útil para SQL/BI ad-hoc y para no acoplar a nadie al nombre físico
-- exacto), NO agrega ningún JOIN ni transformación adicional.
-- ============================================================================

USE `colombia`;

CREATE OR REPLACE VIEW `VW_Elastic_Importaciones` AS
SELECT * FROM `importacion`;
