"""Generador determinístico de labels amigables en español a partir de un
nombre de columna en snake_case.

Contexto: la plataforma de consumo (TradeIntelligence) ya sincroniza
automáticamente cada columna nueva de `colombia.importacion` como
`CampoElastic`, con un label inicial muy simple (sólo capitaliza la primera
palabra: 'pais_origen' -> 'Pais origen', ver
trade_data/scanner/sync.py::humanize_column_name). Ese label es sólo el
valor por defecto: un administrador puede editarlo libremente después y el
escáner nunca lo vuelve a pisar una vez editado.

Este módulo genera un label MEJOR (con acentos y preposiciones correctas en
español) para aplicarlo una única vez, como si fuera la primera edición de
un administrador — así se cumple "no quiero escribir ningún label
manualmente" sin duplicar ni pelear con la lógica de sincronización que ya
existe (ver 05_ETL_Metadata.py).
"""
import re

# Acrónimos de dominio que se mantienen en mayúsculas tal cual (agregar uno
# nuevo es sólo sumar una entrada).
ACRONIMOS = {
    "fob": "FOB", "cif": "CIF", "iva": "IVA", "nit": "NIT", "dian": "DIAN",
    "usd": "USD", "eur": "EUR", "cny": "CNY", "iso": "ISO", "es": "ES",
}

# Palabras que, cuando encabezan una columna y la siguiente palabra no es un
# acrónimo ni ya una preposición, se traducen a "sustantivo + de" (regla que
# reproduce 'fecha_declaracion' -> 'Fecha de Declaración' y, a la vez, deja
# 'valor_fob' -> 'Valor FOB' porque 'fob' sí es acrónimo).
CONECTORES = {
    "fecha": "de", "numero": "de", "num": "de", "nombre": "de",
    "codigo": "de", "valor": "de", "total": "de", "base": "de",
    "porcentaje": "de", "cantidad": "de", "tasa": "de", "documento": "de",
    "digito": "de", "identificacion": "de", "clase": "de", "tipo": "de",
    "modo": "de",
}

# Preposiciones que ya vienen como token literal en el nombre de columna
# (ej. 'manifiesto_de_carga'): se dejan tal cual, en minúscula.
PREPOSICIONES = {"de", "del", "la", "el", "en", "y", "a", "con"}

# Corrección de acentos: snake_case nunca trae tildes, así que se reponen las
# de las palabras de dominio que aparecen en las columnas de este proyecto.
ACENTOS = {
    "declaracion": "declaración", "importacion": "importación",
    "exportacion": "exportación", "informacion": "información",
    "clasificacion": "clasificación", "liquidacion": "liquidación",
    "presentacion": "presentación", "inspeccion": "inspección",
    "aceptacion": "aceptación", "numero": "número", "codigo": "código",
    "economica": "económica", "electronica": "electrónica",
    "municipio": "municipio", "region": "región", "pais": "país",
    "identificacion": "identificación", "declarante": "declarante",
    "arancelaria": "arancelaria", "mercancia": "mercancía",
    "compensatorios": "compensatorios", "salvaguardia": "salvaguardia",
    "publico": "público", "deposito": "depósito", "regimen": "régimen",
    "aereo": "aéreo", "maritimo": "marítimo", "terrestre": "terrestre",
    "anio": "año", "capitulo": "capítulo", "acuerdo": "acuerdo",
    "modalidad": "modalidad", "categoria": "categoría", "posicion": "posición",
}


def humanize_label(nombre_columna: str) -> str:
    """'fecha_declaracion' -> 'Fecha de Declaración'; 'valor_fob' -> 'Valor FOB'."""
    palabras = [p for p in re.split(r"[_\-]+", nombre_columna.strip()) if p]
    if not palabras:
        return nombre_columna

    salida = []
    for idx, palabra in enumerate(palabras):
        minuscula = palabra.lower()

        if minuscula in ACRONIMOS:
            salida.append(ACRONIMOS[minuscula])
            continue
        if minuscula in PREPOSICIONES:
            salida.append(minuscula)
            continue

        minuscula = ACENTOS.get(minuscula, minuscula)
        siguiente = palabras[idx + 1].lower() if idx + 1 < len(palabras) else ""
        if (
            minuscula in CONECTORES
            and siguiente
            and siguiente not in ACRONIMOS
            and siguiente not in PREPOSICIONES
        ):
            salida.append(minuscula.capitalize())
            salida.append(CONECTORES[minuscula])
            continue

        salida.append(minuscula.capitalize())

    label = " ".join(salida)
    return label[0].upper() + label[1:] if label else label
