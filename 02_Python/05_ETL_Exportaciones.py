"""
Fase 4 (Exportaciones): construcción de la tabla física definitiva `colombia.exportacion`.

Lee `temporal_expo` en bloques, resuelve cada valor contra diccionarios cargados
desde `Dimension` e inserta masivamente hacia `exportacion`.
Al finalizar con éxito, encola la tarea en `trade_intelligence.cola_indexacion`
con tipo_intercambio = 'EXPORTACION' y elimina de `temporal_expo` las filas del
archivo procesado.
"""
import argparse
import sys

from common import config, db, checkpoint, geo, cola_indexacion
from common.parsing import parse_fecha, primera_fecha_valida, parse_decimal, parse_entero, limpio
from common.logging_setup import get_logger

logger = get_logger("dw_exportaciones", "dian_dw_exportaciones.log")

TABLA_ORIGEN = "temporal_expo"
FASE = "HECHOS"
COD_DIM_PAIS = 31
CHUNK_SIZE = config.DEFAULT_CHUNK_SIZE

COLUMNAS_ORIGEN = [
    "fecha_declaracion_exportacion", "fech_decla_exportacion_ant", "fech_decla_precedente",
    "fecha_solicitud_auto_embarque", "fecha_proceso",
    "cod_pais_destino_alf", "cod_pais_destino", "pais_destino_final",
    "region_de_origen", "region_procedencia", "ciudad_destinatario",
    "cod_aduana_despacho", "aduana_despacho", "cod_aduana_salida", "aduana_salida",
    "nit_exportador", "razon_social_exportador",
    "razon_social_destinatario",
    "nit_declarante", "razon_social_declarante",
    "subpartida",
    "unidad_fisica",
    "forma_pago",
    "cod_modalidad_exportacion", "modalidad_exportacion",
    "tipo_declaracion", "tipo_despacho", "clase_exportador",
    "modo_transporte", "nacionalidad_bandera", "cod_moneda_transaccion",
    "cantidad_unidades_fisicas", "peso_bruto_kgs", "peso_neto_kgs",
    "valor_fob_usd", "valor_fob_pesos", "vlr_serie_agregado_nal_usd",
    "valor_serie_fletes_usd", "valor_serie_seguros_usd", "vlr_serie_otros_gastos_usd",
    "num_solicitud_auto_embarque", "numero_formulario",
]

COLUMNAS_DESTINO = [
    "fecha_declaracion", "anio", "trimestre", "mes", "nombre_mes", "anio_mes",
    "pais_destino", "pais_destino_nombre", "region_origen", "region_procedencia", "ciudad_destinatario",
    "aduana_despacho", "aduana_salida",
    "exportador", "nit_exportador", "destinatario", "agente_aduanero",
    "partida_arancelaria", "capitulo", "capitulo_nombre",
    "unidad_medida", "forma_pago", "modalidad_exportacion",
    "tipo_declaracion", "tipo_despacho", "clase_exportador", "modo_transporte", "nacionalidad_bandera", "moneda",
    "cantidad", "peso_bruto", "peso_neto",
    "valor_fob_usd", "valor_fob_pesos", "valor_agregado_nacional_usd",
    "valor_fletes_usd", "valor_seguros_usd", "valor_otros_gastos_usd",
    "num_solicitud_auto_embarque", "numero_formulario",
    "archivo_origen",
]

MESES_ES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


class Diccionarios:
    def __init__(self, conn):
        self.aduana = db.load_dict(conn, "SELECT `Codigo`, `Nombre` FROM `Dimension`.`DimAduana` WHERE CodDimPais = %s", (COD_DIM_PAIS,))
        self.exportador = db.load_dict(conn, "SELECT `Nit`, `Nombre` FROM `Dimension`.`DimExportador` WHERE CodDimPais = %s", (COD_DIM_PAIS,))
        self.agente = db.load_dict(conn, "SELECT `Nit`, `Nombre` FROM `Dimension`.`DimAgenteAduanero` WHERE CodDimPais = %s", (COD_DIM_PAIS,))
        self.forma_pago = db.load_dict(conn, "SELECT `Codigo`, `Nombre` FROM `Dimension`.`DimFormaPago` WHERE CodDimPais = %s", (COD_DIM_PAIS,))
        self.tipo_declaracion = db.load_dict(conn, "SELECT `Codigo`, `Nombre` FROM `Dimension`.`DimTipoDeclaracion` WHERE CodDimPais = %s", (COD_DIM_PAIS,))


def _resolver(diccionario: dict, codigo, valor_crudo=None):
    if codigo and codigo in diccionario and diccionario[codigo]:
        return diccionario[codigo]
    if valor_crudo:
        return valor_crudo
    return codigo


def transformar_fila(origen: dict, dicc: Diccionarios, archivo_origen: str) -> tuple:
    fecha = primera_fecha_valida(
        origen["fecha_declaracion_exportacion"], origen["fech_decla_exportacion_ant"],
        origen["fech_decla_precedente"], origen["fecha_solicitud_auto_embarque"], origen["fecha_proceso"]
    )
    anio = fecha.year if fecha else 0
    trimestre = (fecha.month - 1) // 3 + 1 if fecha else None
    mes = fecha.month if fecha else None
    nombre_mes = MESES_ES[fecha.month - 1] if fecha else None
    anio_mes = f"{fecha.year:04d}-{fecha.month:02d}" if fecha else None

    pais_destino_raw = limpio(origen["pais_destino_final"]) or limpio(origen["cod_pais_destino_alf"]) or limpio(origen["cod_pais_destino"])
    pais_destino_iso = geo.resolver_iso2(pais_destino_raw)

    subpartida = limpio(origen["subpartida"])
    capitulo, capitulo_nombre = geo.resolver_capitulo(subpartida)

    nit_exportador = limpio(origen["nit_exportador"])
    nombre_exportador_crudo = limpio(origen["razon_social_exportador"])

    nit_agente = limpio(origen["nit_declarante"])
    nombre_agente_crudo = limpio(origen["razon_social_declarante"])

    return (
        fecha, anio, trimestre, mes, nombre_mes, anio_mes,
        pais_destino_iso, pais_destino_raw,
        limpio(origen["region_de_origen"]), limpio(origen["region_procedencia"]), limpio(origen["ciudad_destinatario"]),
        _resolver(dicc.aduana, limpio(origen["cod_aduana_despacho"]), limpio(origen["aduana_despacho"])),
        _resolver(dicc.aduana, limpio(origen["cod_aduana_salida"]), limpio(origen["aduana_salida"])),
        _resolver(dicc.exportador, nit_exportador, nombre_exportador_crudo), nit_exportador,
        limpio(origen["razon_social_destinatario"]),
        _resolver(dicc.agente, nit_agente, nombre_agente_crudo),
        subpartida, capitulo, capitulo_nombre,
        limpio(origen["unidad_fisica"]),
        _resolver(dicc.forma_pago, limpio(origen["forma_pago"])),
        limpio(origen["modalidad_exportacion"]) or limpio(origen["cod_modalidad_exportacion"]),
        _resolver(dicc.tipo_declaracion, limpio(origen["tipo_declaracion"])),
        limpio(origen["tipo_despacho"]),
        limpio(origen["clase_exportador"]),
        limpio(origen["modo_transporte"]),
        limpio(origen["nacionalidad_bandera"]),
        limpio(origen["cod_moneda_transaccion"]) or "USD",
        parse_decimal(origen["cantidad_unidades_fisicas"]),
        parse_decimal(origen["peso_bruto_kgs"]),
        parse_decimal(origen["peso_neto_kgs"]),
        parse_decimal(origen["valor_fob_usd"]),
        parse_decimal(origen["valor_fob_pesos"]),
        parse_decimal(origen["vlr_serie_agregado_nal_usd"]),
        parse_decimal(origen["valor_serie_fletes_usd"]),
        parse_decimal(origen["valor_serie_seguros_usd"]),
        parse_decimal(origen["vlr_serie_otros_gastos_usd"]),
        limpio(origen["num_solicitud_auto_embarque"]),
        limpio(origen["numero_formulario"]),
        archivo_origen,
    )


def procesar_archivo(conn, dicc: Diccionarios, archivo: str) -> int:
    with conn.cursor() as cursor:
        cursor.execute("SHOW COLUMNS FROM `temporal_expo`")
        existing_cols = {row[0].lower() for row in cursor.fetchall()}

    col_selects = [f"`{c}`" if c in existing_cols else f"NULL AS `{c}`" for c in COLUMNAS_ORIGEN]
    columnas_sql = ", ".join(col_selects)
    insert_sql = (
        f"INSERT INTO `exportacion` ({', '.join(f'`{c}`' for c in COLUMNAS_DESTINO)}) "
        f"VALUES ({', '.join(['%s'] * len(COLUMNAS_DESTINO))})"
    )

    total = 0
    with conn.cursor() as cursor_write:
        cursor_write.execute("DELETE FROM `exportacion` WHERE `archivo_origen` = %s", (archivo,))

    # Cursor de lectura separado del de escritura: ejecutar el INSERT sobre el
    # mismo cursor que tiene abierto el SELECT descarta su resultset en
    # pymysql (fetchmany() siguiente vuelve vacío), cortando el bucle tras el
    # primer CHUNK_SIZE aunque queden filas por procesar.
    with conn.cursor() as cursor_read, conn.cursor() as cursor_write:
        cursor_read.execute(f"SELECT {columnas_sql} FROM `temporal_expo` WHERE archivo_origen = %s", (archivo,))
        while True:
            filas = cursor_read.fetchmany(CHUNK_SIZE)
            if not filas:
                break
            lote = []
            for fila in filas:
                origen = dict(zip(COLUMNAS_ORIGEN, fila))
                lote.append(transformar_fila(origen, dicc, archivo))
            cursor_write.executemany(insert_sql, lote)
            total += len(lote)
            logger.debug(f"'{archivo}': {total} filas insertadas en 'exportacion' hasta ahora.")
    conn.commit()
    return total



def _asegurar_tabla_exportacion(conn):
    sql = """
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
      `exportador`                  VARCHAR(255) NULL,
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
    """
    sql_control = """
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
    """
    with conn.cursor() as cursor:
        cursor.execute(sql)
        cursor.execute(sql_control)
    conn.commit()



def main():
    parser = argparse.ArgumentParser(description="Fase 4 Exportaciones: construcción de la tabla física 'exportacion'.")
    parser.add_argument("--archivo", default=None, help="Procesa únicamente este archivo_origen (por defecto: todos los pendientes).")
    args = parser.parse_args()

    logger.info("=== Iniciando Fase 4: tabla 'exportacion' ===")
    conn = db.get_connection(database=config.MYSQL_DATABASE)
    try:
        _asegurar_tabla_exportacion(conn)
        archivos = [args.archivo] if args.archivo else checkpoint.archivos_pendientes(conn, TABLA_ORIGEN, FASE)
        if not archivos:
            logger.info("No hay archivos pendientes para la Fase 4 (Exportaciones).")
            return

        logger.info(f"{len(archivos)} archivo(s) pendiente(s) para cargar en 'exportacion'.")
        hubo_error = False
        for archivo in archivos:
            logger.info(f"--- Procesando hechos de '{archivo}' ---")
            inicio = checkpoint.marcar_inicio(conn, TABLA_ORIGEN, archivo, FASE)
            try:
                dicc = Diccionarios(conn)
                total = procesar_archivo(conn, dicc, archivo)
                checkpoint.marcar_exito(conn, TABLA_ORIGEN, archivo, FASE, total, inicio)
                logger.info(f"'{archivo}': {total} filas cargadas en 'exportacion'.")
                cola_indexacion.encolar_exportacion(conn, archivo)
                logger.info(f"'{archivo}': encolado para indexación de Exportaciones en Elasticsearch.")

                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM `temporal_expo` WHERE `archivo_origen` = %s", (archivo,))
                conn.commit()
                logger.info(f"'{archivo}': eliminadas sus filas crudas de 'temporal_expo'.")
            except Exception as e:
                hubo_error = True
                conn.rollback()
                checkpoint.marcar_error(conn, TABLA_ORIGEN, archivo, FASE, str(e))
                logger.error(f"Error cargando hechos de '{archivo}': {e}", exc_info=True)

        logger.info("=== Fase 4 Exportaciones completada ===")
        if hubo_error:
            sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
