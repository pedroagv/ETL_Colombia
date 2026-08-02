"""
Fase 3: Construcción/población automática de dimensiones.

Analiza `temporal_impo` y puebla las dimensiones necesarias en la base de
datos COMPARTIDA `Dimension` (reutilizada entre todos los países del Data
Warehouse; ver 01_SQL/01_Dimensiones.sql y Modelo_Dimensional.md para la
justificación completa de cardinalidad/reutilización detrás de cada una).

Principios de esta fase (ver reglas obligatorias del proyecto):
  - Nunca cursores, nunca WHILE, nunca SELECT por registro: cada dimensión
    se puebla con UN `INSERT IGNORE ... SELECT DISTINCT` set-based.
  - Incremental: se procesa un `archivo_origen` a la vez (los ya
    procesados con éxito se saltan, ver `etl_control_carga`), nunca se
    vuelve a escanear toda `temporal_impo` en cada corrida.
  - Idempotente: INSERT IGNORE sobre la UNIQUE KEY de cada dimensión; volver
    a correr el mismo archivo nunca duplica una fila.
  - CodDimPais = 31 (COLOMBIA, confirmado contra `Dimension.DimPais`) en
    todas las dimensiones nuevas/reutilizadas que se scopean por país.
"""
import argparse
import sys

from common import config, db, checkpoint
from common.logging_setup import get_logger

logger = get_logger("dw_dimensiones", "dian_dw_dimensiones.log")

TABLA_ORIGEN = "temporal_impo"
FASE = "DIMENSIONES"
COD_DIM_PAIS_COLOMBIA = 31

# ----------------------------------------------------------------------------
# Reglas de población: (nombre para logs, SQL parametrizado por archivo_origen).
# Cada `%s` de la subconsulta corresponde a un `archivo_origen` (mismo valor
# repetido tantas veces como ramas UNION ALL tenga la regla).
# ----------------------------------------------------------------------------

def _regla(nombre: str, sql: str, n_placeholders: int) -> dict:
    return {"nombre": nombre, "sql": sql, "n": n_placeholders}


REGLAS = [
    _regla(
        "DimDepartamento",
        """
        INSERT IGNORE INTO `Dimension`.`DimDepartamento` (`Codigo`, `Nombre`, `CodDimPais`)
        SELECT codigo_departamento, MIN(nombre_departamento), 31
        FROM (
          SELECT NULLIF(TRIM(cod_departamento_destino),'') codigo_departamento, NULLIF(TRIM(departamento_destino),'') nombre_departamento
          FROM `colombia`.`temporal_impo` WHERE archivo_origen = %s
          UNION ALL
          SELECT NULLIF(TRIM(codigo_depto_importador),''), NULLIF(TRIM(departamento_importador),'')
          FROM `colombia`.`temporal_impo` WHERE archivo_origen = %s
        ) u
        WHERE codigo_departamento IS NOT NULL
        GROUP BY codigo_departamento
        """,
        2,
    ),
    _regla(
        "DimMunicipio",
        """
        INSERT IGNORE INTO `Dimension`.`DimMunicipio` (`Codigo`, `Nombre`, `CodDimPais`)
        SELECT DISTINCT NULLIF(TRIM(codigo_municipio),''), NULL, 31
        FROM `colombia`.`temporal_impo`
        WHERE archivo_origen = %s AND codigo_municipio IS NOT NULL AND TRIM(codigo_municipio) <> ''
        """,
        1,
    ),
    _regla(
        "DimEmpresaTransportadora",
        """
        INSERT IGNORE INTO `Dimension`.`DimEmpresaTransportadora` (`Nombre`, `CodDimPais`)
        SELECT DISTINCT UPPER(TRIM(empresa_transportadora)), 31
        FROM `colombia`.`temporal_impo`
        WHERE archivo_origen = %s AND empresa_transportadora IS NOT NULL AND TRIM(empresa_transportadora) <> ''
        """,
        1,
    ),
    _regla(
        "DimBanco",
        """
        INSERT IGNORE INTO `Dimension`.`DimBanco` (`Codigo`, `Nombre`, `CodDimPais`)
        SELECT DISTINCT NULLIF(TRIM(banc_codigo_banco),''), NULL, 31
        FROM `colombia`.`temporal_impo`
        WHERE archivo_origen = %s AND banc_codigo_banco IS NOT NULL AND TRIM(banc_codigo_banco) <> ''
        """,
        1,
    ),
    _regla(
        "DimFormaPago",
        """
        INSERT IGNORE INTO `Dimension`.`DimFormaPago` (`Codigo`, `Nombre`, `CodDimPais`)
        SELECT codigo_forma_pago, MIN(nombre_forma_pago), 31
        FROM (
          SELECT NULLIF(TRIM(cod_forma_pago),'') codigo_forma_pago, NULLIF(TRIM(forma_pago),'') nombre_forma_pago
          FROM `colombia`.`temporal_impo` WHERE archivo_origen = %s
        ) u
        WHERE codigo_forma_pago IS NOT NULL
        GROUP BY codigo_forma_pago
        """,
        1,
    ),
    _regla(
        "DimTipoDeclaracion",
        """
        INSERT IGNORE INTO `Dimension`.`DimTipoDeclaracion` (`Codigo`, `Nombre`, `CodDimPais`)
        SELECT codigo_tipo_declaracion, MIN(nombre_tipo_declaracion), 31
        FROM (
          SELECT NULLIF(TRIM(cod_tipo_declaracion),'') codigo_tipo_declaracion, NULLIF(TRIM(tipo_declaracion),'') nombre_tipo_declaracion
          FROM `colombia`.`temporal_impo` WHERE archivo_origen = %s
        ) u
        WHERE codigo_tipo_declaracion IS NOT NULL
        GROUP BY codigo_tipo_declaracion
        """,
        1,
    ),
    _regla(
        "DimClaseImportador",
        """
        INSERT IGNORE INTO `Dimension`.`DimClaseImportador` (`Codigo`, `Nombre`, `CodDimPais`)
        SELECT codigo_clase_importador, MIN(nombre_clase_importador), 31
        FROM (
          SELECT NULLIF(TRIM(cod_clase_importador),'') codigo_clase_importador, NULLIF(TRIM(clase_importador),'') nombre_clase_importador
          FROM `colombia`.`temporal_impo` WHERE archivo_origen = %s
        ) u
        WHERE codigo_clase_importador IS NOT NULL
        GROUP BY codigo_clase_importador
        """,
        1,
    ),
    _regla(
        "DimTipoImportacion",
        """
        INSERT IGNORE INTO `Dimension`.`DimTipoImportacion` (`Codigo`, `Nombre`, `CodDimPais`)
        SELECT codigo_tipo_importacion, MIN(nombre_tipo_importacion), 31
        FROM (
          SELECT NULLIF(TRIM(cod_tipo_importacion),'') codigo_tipo_importacion, NULLIF(TRIM(tipo_importacion),'') nombre_tipo_importacion
          FROM `colombia`.`temporal_impo` WHERE archivo_origen = %s
        ) u
        WHERE codigo_tipo_importacion IS NOT NULL
        GROUP BY codigo_tipo_importacion
        """,
        1,
    ),
    _regla(
        "DimEmbalaje",
        """
        INSERT IGNORE INTO `Dimension`.`DimEmbalaje` (`Codigo`, `Nombre`, `CodDimPais`)
        SELECT codigo_embalaje, MIN(nombre_embalaje), 31
        FROM (
          SELECT NULLIF(TRIM(codigo_embalaje),'') codigo_embalaje, NULLIF(TRIM(clase_de_embalaje),'') nombre_embalaje
          FROM `colombia`.`temporal_impo` WHERE archivo_origen = %s
        ) u
        WHERE codigo_embalaje IS NOT NULL
        GROUP BY codigo_embalaje
        """,
        1,
    ),
    _regla(
        "DimEntidadIntermedia",
        """
        INSERT IGNORE INTO `Dimension`.`DimEntidadIntermedia` (`Codigo`, `Nombre`, `CodDimPais`)
        SELECT DISTINCT NULLIF(TRIM(codigo_entidad_intermedia),''), NULL, 31
        FROM `colombia`.`temporal_impo`
        WHERE archivo_origen = %s AND codigo_entidad_intermedia IS NOT NULL AND TRIM(codigo_entidad_intermedia) <> ''
        """,
        1,
    ),
    _regla(
        "DimDeposito",
        """
        INSERT IGNORE INTO `Dimension`.`DimDeposito` (`Codigo`, `Nombre`, `CodDimPais`)
        SELECT DISTINCT NULLIF(TRIM(codigo_deposito),''), NULL, 31
        FROM `colombia`.`temporal_impo`
        WHERE archivo_origen = %s AND codigo_deposito IS NOT NULL AND TRIM(codigo_deposito) <> ''
        """,
        1,
    ),
    _regla(
        "DimActividadEconomica",
        """
        INSERT IGNORE INTO `Dimension`.`DimActividadEconomica` (`Codigo`, `Nombre`, `CodDimPais`)
        SELECT DISTINCT NULLIF(TRIM(actividad_economica_sec),''), NULL, 31
        FROM `colombia`.`temporal_impo`
        WHERE archivo_origen = %s AND actividad_economica_sec IS NOT NULL AND TRIM(actividad_economica_sec) <> ''
        """,
        1,
    ),
    _regla(
        "DimModalidad",
        """
        INSERT IGNORE INTO `Dimension`.`DimModalidad` (`CodigoModalidad`, `CodigoSubModalidad`, `Nombre`, `CodDimPais`)
        SELECT codigo_modalidad, codigo_sub_modalidad, NULL, 31
        FROM (
          SELECT DISTINCT
            NULLIF(TRIM(moda_codigo_modalidad),'') AS codigo_modalidad,
            NULLIF(TRIM(cod_modalidad_importacion),'') AS codigo_sub_modalidad
          FROM `colombia`.`temporal_impo` WHERE archivo_origen = %s
        ) u
        WHERE codigo_modalidad IS NOT NULL AND codigo_sub_modalidad IS NOT NULL
        """,
        1,
    ),
    # --- Dimensiones YA EXISTENTES en `Dimension` que Colombia reutiliza ---
    _regla(
        "DimAduana",
        """
        INSERT IGNORE INTO `Dimension`.`DimAduana` (`Codigo`, `Nombre`, `CodDimPais`)
        SELECT codigo_aduana, MIN(nombre_aduana), 31
        FROM (
          SELECT NULLIF(TRIM(cod_aduana_presentada),'') codigo_aduana, NULLIF(TRIM(aduana_presentada),'') nombre_aduana
          FROM `colombia`.`temporal_impo` WHERE archivo_origen = %s
          UNION ALL
          SELECT NULLIF(TRIM(cod_administracion_presentada_1),''), NULLIF(TRIM(nombre_aduana_1),'')
          FROM `colombia`.`temporal_impo` WHERE archivo_origen = %s
          UNION ALL
          SELECT NULLIF(TRIM(cod_aduana_anterior),''), NULL
          FROM `colombia`.`temporal_impo` WHERE archivo_origen = %s
          UNION ALL
          SELECT NULLIF(TRIM(cod_aduana_export),''), NULL
          FROM `colombia`.`temporal_impo` WHERE archivo_origen = %s
          UNION ALL
          SELECT NULLIF(TRIM(cod_lugar_ingreso_mcia),''), NULLIF(TRIM(lugar_ingreso_mcia),'')
          FROM `colombia`.`temporal_impo` WHERE archivo_origen = %s
        ) u
        WHERE codigo_aduana IS NOT NULL
        GROUP BY codigo_aduana
        """,
        5,
    ),
    _regla(
        "DimImportador",
        """
        INSERT IGNORE INTO `Dimension`.`DimImportador` (`Nit`, `Nombre`, `Direccion`, `Telefono`, `CodDimPais`)
        SELECT nit_importador, MIN(nombre), MIN(direccion), MIN(telefono), 31
        FROM (
          SELECT
            NULLIF(TRIM(nit_importador),'') AS nit_importador,
            NULLIF(TRIM(nombre_importador),'') AS nombre,
            direccion_importador AS direccion,
            telefono_importador AS telefono
          FROM `colombia`.`temporal_impo`
          WHERE archivo_origen = %s AND nit_importador IS NOT NULL AND TRIM(nit_importador) <> ''
        ) u
        GROUP BY nit_importador
        """,
        1,
    ),
    # `numero_identificac_export` viene VACÍO en el 100% de los registros
    # reales (confirmado contra la BD): el exportador extranjero no tiene
    # NIT colombiano, algo esperable en declaraciones de importación. Se usa
    # el nombre normalizado como clave natural de respaldo cuando no hay NIT
    # (mismo patrón que DimEmpresaTransportadora), para no romper la
    # deduplicación por UNIQUE KEY (NULL no deduplica en MySQL).
    _regla(
        "DimExportador",
        """
        INSERT IGNORE INTO `Dimension`.`DimExportador` (`Nit`, `Nombre`, `Direccion`, `CodDimPais`)
        SELECT nit_exportador, MIN(nombre), MIN(direccion), 31
        FROM (
          SELECT
            COALESCE(NULLIF(TRIM(numero_identificac_export),''), CONCAT('NOMBRE:', UPPER(TRIM(nombre_exportador)))) AS nit_exportador,
            NULLIF(TRIM(nombre_exportador),'') AS nombre,
            direccion_exportador AS direccion
          FROM `colombia`.`temporal_impo`
          WHERE archivo_origen = %s AND nombre_exportador IS NOT NULL AND TRIM(nombre_exportador) <> ''
        ) u
        GROUP BY nit_exportador
        """,
        1,
    ),
    _regla(
        "DimAgenteAduanero",
        """
        INSERT IGNORE INTO `Dimension`.`DimAgenteAduanero` (`Nit`, `Nombre`, `CodDimPais`)
        SELECT nit_agente, MIN(nombre_agente), 31
        FROM (
          SELECT
            NULLIF(TRIM(COALESCE(NULLIF(TRIM(nit_declarante),''), NULLIF(TRIM(docto_identif_declar),''))),'') AS nit_agente,
            NULLIF(TRIM(COALESCE(NULLIF(TRIM(nombre_declarante),''), NULLIF(TRIM(razon_social_declarante),''))),'') AS nombre_agente
          FROM `colombia`.`temporal_impo` WHERE archivo_origen = %s
        ) u
        WHERE nit_agente IS NOT NULL
        GROUP BY nit_agente
        """,
        1,
    ),
    _regla(
        "DimPartidas",
        """
        INSERT IGNORE INTO `Dimension`.`DimPartidas` (`HS10`, `HS2`, `HS4`, `HS6`, `HS8`, `CodDimPais`)
        SELECT codigo, LEFT(codigo,2), LEFT(codigo,4), LEFT(codigo,6), LEFT(codigo,8), 31
        FROM (
          SELECT DISTINCT NULLIF(TRIM(subpartida_arancelaria),'') AS codigo
          FROM `colombia`.`temporal_impo` WHERE archivo_origen = %s
        ) u
        WHERE codigo IS NOT NULL
        """,
        1,
    ),
]


def procesar_archivo(conn_colombia, archivo: str) -> int:
    """Ejecuta todas las reglas de población para un único archivo_origen.
    Devuelve la cantidad de reglas ejecutadas (no de filas: cada regla es un
    INSERT masivo, no hay forma de contar "registros" 1:1 con el origen).

    NOTA: `DimPais` NO se puebla desde aquí. Es una tabla compartida entre
    todos los países del Data Warehouse, ya poblada (524 filas) y con texto
    de nombre poco predecible entre orígenes (la DIAN usa nombres oficiales
    largos, ej. "COREA (SUR) REPÚBLICA DE", que no coinciden con el texto
    usado por otros países); insertar variantes de texto ahí arriesgaría
    duplicar países bajo distintos nombres. El ISO2 que necesita
    `importacion.pais_origen` se resuelve en la Fase 4 con un catálogo
    estático propio (`common/geo.py`), sin tocar `Dimension.DimPais`."""
    with conn_colombia.cursor() as cursor:
        for regla in REGLAS:
            params = tuple([archivo] * regla["n"])
            cursor.execute(regla["sql"], params)
    conn_colombia.commit()
    return len(REGLAS)


def main():
    parser = argparse.ArgumentParser(description="Fase 3: población de dimensiones en la base de datos compartida 'Dimension'.")
    parser.add_argument("--archivo", default=None, help="Procesa únicamente este archivo_origen (por defecto: todos los pendientes).")
    args = parser.parse_args()

    logger.info("=== Iniciando Fase 3: Dimensiones ===")
    conn = db.get_connection(database=config.MYSQL_DATABASE)
    try:
        archivos = [args.archivo] if args.archivo else checkpoint.archivos_pendientes(conn, TABLA_ORIGEN, FASE)
        if not archivos:
            logger.info("No hay archivos pendientes para la Fase 3 (Dimensiones).")
            return

        logger.info(f"{len(archivos)} archivo(s) pendiente(s) para poblar dimensiones.")
        for archivo in archivos:
            logger.info(f"--- Procesando dimensiones de '{archivo}' ---")
            inicio = checkpoint.marcar_inicio(conn, TABLA_ORIGEN, archivo, FASE)
            try:
                n_reglas = procesar_archivo(conn, archivo)
                checkpoint.marcar_exito(conn, TABLA_ORIGEN, archivo, FASE, n_reglas, inicio)
                logger.info(f"'{archivo}': {n_reglas} reglas de dimensión aplicadas.")
            except Exception as e:
                conn.rollback()
                checkpoint.marcar_error(conn, TABLA_ORIGEN, archivo, FASE, str(e))
                logger.error(f"Error poblando dimensiones para '{archivo}': {e}", exc_info=True)

        logger.info("=== Fase 3 completada ===")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
