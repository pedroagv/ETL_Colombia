"""Despliega (crea/actualiza) los Stored Procedures de `colombia` definidos
en `01_SQL/06_Procedimientos.sql` (sp_agregar_particion_anual,
sp_extraer_importacion_por_archivo — este último lo consume el worker de
'indexacion', ver proyectos/indexacion/README.md).

Reusa la misma conexión/config que el resto de las Fases 3-4
(common.config / common.db) — correrlo contra un ambiente nuevo (ej.
producción) es solo apuntar el `.env` de ese ambiente y ejecutar este
script ahí.

Uso:
    python desplegar_procedimientos.py
"""
import os
import re

from common import config, db

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SQL_PATH = os.path.join(_SCRIPT_DIR, "..", "01_SQL", "06_Procedimientos.sql")



def _extraer_statements(sql_texto: str) -> list[str]:
    """Separa el archivo DELIMITER $$ ... DELIMITER ; en statements
    individuales (pymysql no soporta DELIMITER, hay que partir por '$$' a mano)."""
    cuerpo = re.search(r"DELIMITER \$\$(.*)DELIMITER ;", sql_texto, re.S).group(1)
    return [s.strip() for s in cuerpo.split("$$") if s.strip()]


def main():
    with open(_SQL_PATH, encoding="utf-8") as f:
        sql_texto = f.read()

    statements = _extraer_statements(sql_texto)
    print(f"{len(statements)} statement(s) a ejecutar en '{config.MYSQL_DATABASE}'.")

    conn = db.get_connection(database=config.MYSQL_DATABASE)
    try:
        with conn.cursor() as cur:
            for stmt in statements:
                cur.execute(stmt)
                primera_linea = stmt.strip().splitlines()[0][:80]
                print(f"  ✔ {primera_linea}")
        conn.commit()
        print("Listo.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
