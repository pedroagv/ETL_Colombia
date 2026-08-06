"""
Fase 4: construcción de la tabla física definitiva `colombia.importacion`.

Lee `temporal_impo` en bloques (fetchmany, nunca la tabla completa en
memoria), resuelve cada valor contra diccionarios cargados UNA SOLA VEZ
desde `Dimension` (nunca un SELECT por registro) y hace INSERT masivo hacia
`importacion`. Idempotente: antes de insertar, borra por `archivo_origen`
(mismo patrón ya usado por 02_ETL_SQL.py sobre `temporal_impo`), así que
reprocesar el mismo archivo nunca duplica filas.

Grano: un ítem/subpartida de una declaración de importación (una fila de
`temporal_impo` = una fila de `importacion`).
"""
import argparse
import sys

from common import config, db, checkpoint, geo, cola_indexacion
from common.parsing import parse_fecha, primera_fecha_valida, parse_decimal, parse_entero, limpio
from common.logging_setup import get_logger

logger = get_logger("dw_importaciones", "dian_dw_importaciones.log")

TABLA_ORIGEN = "temporal_impo"
FASE = "HECHOS"
COD_DIM_PAIS = 31
CHUNK_SIZE = config.DEFAULT_CHUNK_SIZE

# Columnas de `temporal_impo` que necesita el transform, en el orden en que
# se seleccionan (ver `_construir_select`).
COLUMNAS_ORIGEN = [
    "fecha_aceptacion_declaracion", "fecha_presentacion", "fecha_manifiesto",
    "fecha_declaracion_ant", "fecha_documento_transp", "fecha_declara_cambio",
    "fecha_factura", "fecha_declaracion_export", "fecha_recibo_pago_anterior",
    "pais_origen", "pais_procedencia", "pais_compra", "pais_exportador", "bandera_transporte",
    "cod_departamento_destino", "departamento_destino",
    "codigo_depto_importador", "departamento_importador",
    "codigo_municipio",
    "cod_aduana_presentada", "cod_administracion_presentada_1", "aduana_presentada", "nombre_aduana_1",
    "cod_aduana_anterior", "cod_aduana_export",
    "nit_importador", "nombre_importador",
    "numero_identificac_export", "nombre_exportador",
    "nit_declarante", "docto_identif_declar", "nombre_declarante", "razon_social_declarante",
    "empresa_transportadora",
    "subpartida_arancelaria",
    "unidad_comercial",
    "cod_forma_pago", "forma_pago",
    "banc_codigo_banco",
    "moda_codigo_modalidad", "cod_modalidad_importacion",
    "cod_tipo_declaracion", "tipo_declaracion",
    "cod_clase_importador", "clase_importador",
    "cod_tipo_importacion", "tipo_importacion",
    "modo_transporte",
    "codigo_embalaje", "clase_de_embalaje",
    "codigo_acuerdo",
    "codigo_entidad_intermedia",
    "codigo_deposito",
    "actividad_economica_sec",
    "peso_neto", "peso_bruto", "cantidad", "cantidad_subpartidas", "numero_bultos", "tasa_cambio", "num_cuotas_o_meses",
    "valor_fob_usd", "valor_cif_usd", "valor_aduana_usd", "valor_ajuste_usd",
    "valor_fletes_usd", "valor_seguros_usd", "valor_otros_gastos_usd", "fletes_seguros1", "valor_cuota_usd",
    "porcentaje_arancel", "base_arancel", "total_liquidado_arancel", "total_a_pagar_arancel",
    "porcentaje_iva", "base_iva", "total_liquidado_iva", "total_a_pagar_iva",
    "porcentaje_otros1", "base_otros1", "subtotal_otros1", "valor_total_otros", "otros_pagados",
    "porcentaje_sancion", "base_sancion", "total_liquidado_sancion", "total_a_pagar_sancion",
    "porcentaje_salvaguardia", "base_salvaguardia", "total_liquidado_salvaguardia", "total_a_pagar_salvaguardia",
    "porcentaje_derechos_comp", "base_derechos_comp", "total_liquidado_derechos_comp", "total_a_pagar_derechos_comp",
    "porcentaje_antidumping", "base_antidumping", "total_liquidado_antidumping", "total_a_pagar_antidumping",
    "porcentaje_rescate", "base_rescate", "total_liquidado_rescate", "total_a_pagar_rescate",
    "total_item1", "valor_total_arancel", "valor_total_iva", "total_liquidado", "pago_total", "valor_pagos_anteriores",
    "numero_formulario", "num_aceptacion_declaracion", "numero_factura", "documento_transporte", "manifiesto_de_carga",
    "descripcion_mercancia",
]

COLUMNAS_DESTINO = [
    "fecha_declaracion", "anio", "trimestre", "mes", "nombre_mes", "anio_mes",
    "pais_origen", "pais_origen_nombre", "pais_procedencia", "pais_compra", "pais_exportador", "bandera_transporte",
    "departamento_destino", "departamento_importador", "municipio",
    "aduana_presentada", "aduana_anterior", "aduana_exportacion",
    "importador", "nit_importador", "exportador", "agente_aduanero", "empresa_transportadora",
    "partida_arancelaria", "capitulo", "capitulo_nombre",
    "unidad_medida", "forma_pago", "banco", "regimen_aduanero",
    "tipo_declaracion", "clase_importador", "tipo_importacion", "modo_transporte", "embalaje",
    "acuerdo_comercial", "entidad_intermedia", "deposito", "actividad_economica", "moneda",
    "peso_neto", "peso_bruto", "cantidad", "cantidad_subpartidas", "numero_bultos", "tasa_cambio", "num_cuotas_o_meses",
    "valor_fob_usd", "valor_cif_usd", "valor_aduana_usd", "valor_ajuste_usd",
    "valor_fletes_usd", "valor_seguros_usd", "valor_otros_gastos_usd", "fletes_seguros1", "valor_cuota_usd",
    "porcentaje_arancel", "base_arancel", "total_liquidado_arancel", "total_a_pagar_arancel",
    "porcentaje_iva", "base_iva", "total_liquidado_iva", "total_a_pagar_iva",
    "porcentaje_otros1", "base_otros1", "subtotal_otros1", "valor_total_otros", "otros_pagados",
    "porcentaje_sancion", "base_sancion", "total_liquidado_sancion", "total_a_pagar_sancion",
    "porcentaje_salvaguardia", "base_salvaguardia", "total_liquidado_salvaguardia", "total_a_pagar_salvaguardia",
    "porcentaje_derechos_comp", "base_derechos_comp", "total_liquidado_derechos_comp", "total_a_pagar_derechos_comp",
    "porcentaje_antidumping", "base_antidumping", "total_liquidado_antidumping", "total_a_pagar_antidumping",
    "porcentaje_rescate", "base_rescate", "total_liquidado_rescate", "total_a_pagar_rescate",
    "total_item1", "valor_total_arancel", "valor_total_iva", "total_liquidado", "pago_total", "valor_pagos_anteriores",
    "numero_formulario", "num_aceptacion_declaracion", "numero_factura", "documento_transporte", "manifiesto_de_carga",
    "descripcion_mercancia",
    "archivo_origen",
]

MESES_ES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


class Diccionarios:
    """Todos los diccionarios de resolución, cargados UNA sola vez por
    ejecución desde `Dimension` (ver reglas obligatorias del proyecto:
    'resolver dimensiones mediante diccionarios Python', 'nunca SELECT por
    registro'). Instanciar de nuevo por cada archivo procesado es barato
    (estas tablas son pequeñas) y garantiza ver los naturales que la Fase 3
    acaba de insertar para ese mismo archivo."""

    def __init__(self, conn):
        self.departamento = self._cargar(conn, "DimDepartamento", "Codigo", "Nombre")
        self.municipio = self._cargar(conn, "DimMunicipio", "Codigo", "Nombre")
        self.aduana = self._cargar(conn, "DimAduana", "Codigo", "Nombre")
        self.importador = self._cargar(conn, "DimImportador", "Nit", "Nombre")
        self.exportador = self._cargar(conn, "DimExportador", "Nit", "Nombre")
        self.agente = self._cargar(conn, "DimAgenteAduanero", "Nit", "Nombre")
        self.banco = self._cargar(conn, "DimBanco", "Codigo", "Nombre")
        self.forma_pago = self._cargar(conn, "DimFormaPago", "Codigo", "Nombre")
        self.tipo_declaracion = self._cargar(conn, "DimTipoDeclaracion", "Codigo", "Nombre")
        self.clase_importador = self._cargar(conn, "DimClaseImportador", "Codigo", "Nombre")
        self.tipo_importacion = self._cargar(conn, "DimTipoImportacion", "Codigo", "Nombre")
        self.embalaje = self._cargar(conn, "DimEmbalaje", "Codigo", "Nombre")
        self.entidad_intermedia = self._cargar(conn, "DimEntidadIntermedia", "Codigo", "Nombre")
        self.deposito = self._cargar(conn, "DimDeposito", "Codigo", "Nombre")
        self.actividad_economica = self._cargar(conn, "DimActividadEconomica", "Codigo", "Nombre")
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT CodigoModalidad, CodigoSubModalidad, Nombre FROM `Dimension`.`DimModalidad` WHERE CodDimPais = %s",
                (COD_DIM_PAIS,),
            )
            self.modalidad = {(r[0], r[1]): r[2] for r in cursor.fetchall()}

    @staticmethod
    def _cargar(conn, tabla: str, col_codigo: str, col_nombre: str) -> dict:
        return db.load_dict(
            conn,
            f"SELECT `{col_codigo}`, `{col_nombre}` FROM `Dimension`.`{tabla}` WHERE CodDimPais = %s",
            (COD_DIM_PAIS,),
        )


def _resolver(diccionario: dict, codigo, valor_crudo=None):
    """Prefiere el nombre catalogado en la dimensión; si el código no está
    (no debería pasar si la Fase 3 ya corrió) cae al valor crudo del origen,
    y si tampoco hay valor crudo, expone el propio código (mejor que NULL
    para catálogos sin nombre resuelto, ver Metadata.md)."""
    if codigo and codigo in diccionario and diccionario[codigo]:
        return diccionario[codigo]
    if valor_crudo:
        return valor_crudo
    return codigo


def transformar_fila(origen: dict, dicc: Diccionarios, archivo_origen: str) -> tuple:
    fecha = primera_fecha_valida(
        origen["fecha_aceptacion_declaracion"], origen["fecha_presentacion"], origen["fecha_manifiesto"],
    )
    anio = fecha.year if fecha else 0
    trimestre = (fecha.month - 1) // 3 + 1 if fecha else None
    mes = fecha.month if fecha else None
    nombre_mes = MESES_ES[fecha.month - 1] if fecha else None
    anio_mes = f"{fecha.year:04d}-{fecha.month:02d}" if fecha else None

    pais_origen_nombre = limpio(origen["pais_origen"])
    codigo_aduana_presentada = limpio(origen["cod_aduana_presentada"]) or limpio(origen["cod_administracion_presentada_1"])
    nombre_aduana_presentada_crudo = limpio(origen["aduana_presentada"]) or limpio(origen["nombre_aduana_1"])

    nit_importador = limpio(origen["nit_importador"])
    nombre_importador_crudo = limpio(origen["nombre_importador"])
    nit_exportador = limpio(origen["numero_identificac_export"]) or (
        f"NOMBRE:{limpio(origen['nombre_exportador']).upper()}" if limpio(origen["nombre_exportador"]) else None
    )
    nit_agente = limpio(origen["nit_declarante"]) or limpio(origen["docto_identif_declar"])
    nombre_agente_crudo = limpio(origen["nombre_declarante"]) or limpio(origen["razon_social_declarante"])

    subpartida = limpio(origen["subpartida_arancelaria"])
    capitulo, capitulo_nombre = geo.resolver_capitulo(subpartida)

    codigo_modalidad = limpio(origen["moda_codigo_modalidad"])
    codigo_submodalidad = limpio(origen["cod_modalidad_importacion"])
    regimen_aduanero = dicc.modalidad.get((codigo_modalidad, codigo_submodalidad)) or (
        f"{codigo_modalidad}-{codigo_submodalidad}" if codigo_modalidad and codigo_submodalidad else None
    )

    return (
        fecha, anio, trimestre, mes, nombre_mes, anio_mes,
        geo.resolver_iso2(pais_origen_nombre), pais_origen_nombre,
        limpio(origen["pais_procedencia"]), limpio(origen["pais_compra"]), limpio(origen["pais_exportador"]), limpio(origen["bandera_transporte"]),
        _resolver(dicc.departamento, limpio(origen["cod_departamento_destino"]), limpio(origen["departamento_destino"])),
        _resolver(dicc.departamento, limpio(origen["codigo_depto_importador"]), limpio(origen["departamento_importador"])),
        _resolver(dicc.municipio, limpio(origen["codigo_municipio"])),
        _resolver(dicc.aduana, codigo_aduana_presentada, nombre_aduana_presentada_crudo),
        _resolver(dicc.aduana, limpio(origen["cod_aduana_anterior"])),
        _resolver(dicc.aduana, limpio(origen["cod_aduana_export"])),
        _resolver(dicc.importador, nit_importador, nombre_importador_crudo), nit_importador,
        _resolver(dicc.exportador, nit_exportador, limpio(origen["nombre_exportador"])),
        _resolver(dicc.agente, nit_agente, nombre_agente_crudo),
        limpio(origen["empresa_transportadora"]).upper() if limpio(origen["empresa_transportadora"]) else None,
        subpartida, capitulo, capitulo_nombre,
        limpio(origen["unidad_comercial"]),
        _resolver(dicc.forma_pago, limpio(origen["cod_forma_pago"]), limpio(origen["forma_pago"])),
        _resolver(dicc.banco, limpio(origen["banc_codigo_banco"])),
        regimen_aduanero,
        _resolver(dicc.tipo_declaracion, limpio(origen["cod_tipo_declaracion"]), limpio(origen["tipo_declaracion"])),
        _resolver(dicc.clase_importador, limpio(origen["cod_clase_importador"]), limpio(origen["clase_importador"])),
        _resolver(dicc.tipo_importacion, limpio(origen["cod_tipo_importacion"]), limpio(origen["tipo_importacion"])),
        limpio(origen["modo_transporte"]),
        _resolver(dicc.embalaje, limpio(origen["codigo_embalaje"]), limpio(origen["clase_de_embalaje"])),
        limpio(origen["codigo_acuerdo"]),
        _resolver(dicc.entidad_intermedia, limpio(origen["codigo_entidad_intermedia"])),
        _resolver(dicc.deposito, limpio(origen["codigo_deposito"])),
        _resolver(dicc.actividad_economica, limpio(origen["actividad_economica_sec"])),
        "USD",
        parse_decimal(origen["peso_neto"]), parse_decimal(origen["peso_bruto"]), parse_decimal(origen["cantidad"]),
        parse_decimal(origen["cantidad_subpartidas"]), parse_decimal(origen["numero_bultos"]), parse_decimal(origen["tasa_cambio"]),
        parse_entero(origen["num_cuotas_o_meses"]),
        parse_decimal(origen["valor_fob_usd"]), parse_decimal(origen["valor_cif_usd"]), parse_decimal(origen["valor_aduana_usd"]),
        parse_decimal(origen["valor_ajuste_usd"]), parse_decimal(origen["valor_fletes_usd"]), parse_decimal(origen["valor_seguros_usd"]),
        parse_decimal(origen["valor_otros_gastos_usd"]), parse_decimal(origen["fletes_seguros1"]), parse_decimal(origen["valor_cuota_usd"]),
        parse_decimal(origen["porcentaje_arancel"]), parse_decimal(origen["base_arancel"]),
        parse_decimal(origen["total_liquidado_arancel"]), parse_decimal(origen["total_a_pagar_arancel"]),
        parse_decimal(origen["porcentaje_iva"]), parse_decimal(origen["base_iva"]),
        parse_decimal(origen["total_liquidado_iva"]), parse_decimal(origen["total_a_pagar_iva"]),
        parse_decimal(origen["porcentaje_otros1"]), parse_decimal(origen["base_otros1"]),
        parse_decimal(origen["subtotal_otros1"]), parse_decimal(origen["valor_total_otros"]), parse_decimal(origen["otros_pagados"]),
        parse_decimal(origen["porcentaje_sancion"]), parse_decimal(origen["base_sancion"]),
        parse_decimal(origen["total_liquidado_sancion"]), parse_decimal(origen["total_a_pagar_sancion"]),
        parse_decimal(origen["porcentaje_salvaguardia"]), parse_decimal(origen["base_salvaguardia"]),
        parse_decimal(origen["total_liquidado_salvaguardia"]), parse_decimal(origen["total_a_pagar_salvaguardia"]),
        parse_decimal(origen["porcentaje_derechos_comp"]), parse_decimal(origen["base_derechos_comp"]),
        parse_decimal(origen["total_liquidado_derechos_comp"]), parse_decimal(origen["total_a_pagar_derechos_comp"]),
        parse_decimal(origen["porcentaje_antidumping"]), parse_decimal(origen["base_antidumping"]),
        parse_decimal(origen["total_liquidado_antidumping"]), parse_decimal(origen["total_a_pagar_antidumping"]),
        parse_decimal(origen["porcentaje_rescate"]), parse_decimal(origen["base_rescate"]),
        parse_decimal(origen["total_liquidado_rescate"]), parse_decimal(origen["total_a_pagar_rescate"]),
        parse_decimal(origen["total_item1"]), parse_decimal(origen["valor_total_arancel"]), parse_decimal(origen["valor_total_iva"]),
        parse_decimal(origen["total_liquidado"]), parse_decimal(origen["pago_total"]), parse_decimal(origen["valor_pagos_anteriores"]),
        limpio(origen["numero_formulario"]), limpio(origen["num_aceptacion_declaracion"]), limpio(origen["numero_factura"]),
        limpio(origen["documento_transporte"]), limpio(origen["manifiesto_de_carga"]),
        limpio(origen["descripcion_mercancia"]),
        archivo_origen,
    )


def procesar_archivo(conn, dicc: Diccionarios, archivo: str) -> int:
    with conn.cursor() as cursor:
        cursor.execute("SHOW COLUMNS FROM `temporal_impo`")
        existing_cols = {row[0].lower() for row in cursor.fetchall()}

    col_selects = [f"`{c}`" if c in existing_cols else f"NULL AS `{c}`" for c in COLUMNAS_ORIGEN]
    columnas_sql = ", ".join(col_selects)
    insert_sql = (
        f"INSERT INTO `importacion` ({', '.join(f'`{c}`' for c in COLUMNAS_DESTINO)}) "
        f"VALUES ({', '.join(['%s'] * len(COLUMNAS_DESTINO))})"
    )

    total = 0
    with conn.cursor() as cursor_write:
        cursor_write.execute("DELETE FROM `importacion` WHERE `archivo_origen` = %s", (archivo,))

    # Cursor de lectura separado del de escritura: ejecutar el INSERT sobre el
    # mismo cursor que tiene abierto el SELECT descarta su resultset en
    # pymysql (fetchmany() siguiente vuelve vacío), cortando el bucle tras el
    # primer CHUNK_SIZE aunque queden filas por procesar.
    with conn.cursor() as cursor_read, conn.cursor() as cursor_write:
        cursor_read.execute(f"SELECT {columnas_sql} FROM `temporal_impo` WHERE archivo_origen = %s", (archivo,))
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
            logger.debug(f"'{archivo}': {total} filas insertadas en 'importacion' hasta ahora.")
    conn.commit()
    return total



def _asegurar_tabla_importacion(conn):
    sql = """
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
      KEY `idx_importacion_archivo_origen` (`archivo_origen`(191))
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
    parser = argparse.ArgumentParser(description="Fase 4: construcción de la tabla física 'importacion'.")
    parser.add_argument("--archivo", default=None, help="Procesa únicamente este archivo_origen (por defecto: todos los pendientes).")
    args = parser.parse_args()

    logger.info("=== Iniciando Fase 4: tabla 'importacion' ===")
    conn = db.get_connection(database=config.MYSQL_DATABASE)
    try:
        _asegurar_tabla_importacion(conn)
        archivos = [args.archivo] if args.archivo else checkpoint.archivos_pendientes(conn, TABLA_ORIGEN, FASE)
        if not archivos:
            logger.info("No hay archivos pendientes para la Fase 4 (Hechos).")
            return

        logger.info(f"{len(archivos)} archivo(s) pendiente(s) para cargar en 'importacion'.")
        hubo_error = False
        for archivo in archivos:
            logger.info(f"--- Procesando hechos de '{archivo}' ---")
            inicio = checkpoint.marcar_inicio(conn, TABLA_ORIGEN, archivo, FASE)
            try:
                dicc = Diccionarios(conn)  # recarga: puede haber naturales nuevos de la Fase 3 para este archivo
                total = procesar_archivo(conn, dicc, archivo)
                checkpoint.marcar_exito(conn, TABLA_ORIGEN, archivo, FASE, total, inicio)
                logger.info(f"'{archivo}': {total} filas cargadas en 'importacion'.")
                cola_indexacion.encolar_importacion(conn, archivo)
                logger.info(f"'{archivo}': encolado para indexación en Elasticsearch.")

                # Limpieza quirúrgica: una vez insertado en 'importacion' y encolado en 'cola_indexacion',
                # eliminamos de 'temporal_impo' únicamente este archivo_origen.
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM `temporal_impo` WHERE `archivo_origen` = %s", (archivo,))
                conn.commit()
                logger.info(f"'{archivo}': eliminadas sus filas crudas de 'temporal_impo'.")
            except Exception as e:
                hubo_error = True
                conn.rollback()
                checkpoint.marcar_error(conn, TABLA_ORIGEN, archivo, FASE, str(e))
                logger.error(f"Error cargando hechos de '{archivo}': {e}", exc_info=True)

        logger.info("=== Fase 4 completada ===")
        if hubo_error:
            # Código de salida != 0 para que main.py sepa que al menos un
            # archivo falló y no reporte falsamente el ciclo como exitoso.
            sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()

