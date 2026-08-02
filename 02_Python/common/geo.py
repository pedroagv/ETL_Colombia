"""Catálogos estáticos universales usados para enriquecer dimensiones sin
tablas MAP físicas ni JOIN: nombre de país en español (tal como lo escribe
la DIAN) -> ISO2, y capítulo arancelario (2 primeros dígitos del código HS)
-> nombre del capítulo según el Sistema Armonizado de la OMA.

Por qué en Python y no en SQL: son catálogos de referencia universales (no
dependen de ningún país del Data Warehouse), se usan una sola vez por valor
distinto y se resuelven en memoria igual que cualquier otra dimensión.
"""
import unicodedata


def _normalizar(texto: str) -> str:
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", texto)
    sin_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sin_acentos.strip().upper()


# Nombre de país (como aparece en los archivos de la DIAN) -> ISO2.
# La plataforma de consumo (TradeIntelligence) usa el ISO2 para su mapa
# mundial y su catálogo de banderas (trade_data.paises.guess_country_meta).
PAIS_A_ISO2 = {
    "AFGANISTAN": "AF", "ALBANIA": "AL", "ALEMANIA": "DE", "ANDORRA": "AD",
    "ANGOLA": "AO", "ANGUILA": "AI", "ANTIGUA Y BARBUDA": "AG",
    "ANTILLAS HOLANDESAS": "AN", "ARABIA SAUDITA": "SA", "ARGELIA": "DZ",
    "ARGENTINA": "AR", "ARMENIA": "AM", "ARUBA": "AW", "AUSTRALIA": "AU",
    "AUSTRIA": "AT", "AZERBAIYAN": "AZ", "BAHAMAS": "BS", "BAHREIN": "BH",
    "BANGLADESH": "BD", "BARBADOS": "BB", "BELGICA": "BE", "BELICE": "BZ",
    "BENIN": "BJ", "BERMUDAS": "BM", "BIELORRUSIA": "BY", "BOLIVIA": "BO",
    "BOSNIA Y HERZEGOVINA": "BA", "BOTSWANA": "BW", "BRASIL": "BR",
    "BRUNEI": "BN", "BULGARIA": "BG", "BURKINA FASO": "BF", "BURUNDI": "BI",
    "BUTAN": "BT", "CABO VERDE": "CV", "CAMBOYA": "KH", "CAMERUN": "CM",
    "CANADA": "CA", "CATAR": "QA", "KAZAJISTAN": "KZ", "CHAD": "TD",
    "CHILE": "CL", "CHINA": "CN", "CHIPRE": "CY", "CIUDAD DEL VATICANO": "VA",
    "COLOMBIA": "CO", "COMORAS": "KM", "QATAR": "QA", "COREA DEL NORTE": "KP",
    "COREA DEL SUR": "KR", "COSTA DE MARFIL": "CI", "COSTA RICA": "CR",
    "CROACIA": "HR", "CUBA": "CU", "CURAZAO": "CW", "DINAMARCA": "DK",
    "DOMINICA": "DM", "ECUADOR": "EC", "EGIPTO": "EG", "EL SALVADOR": "SV",
    "EMIRATOS ARABES UNIDOS": "AE", "ERITREA": "ER", "ESLOVAQUIA": "SK",
    "ESLOVENIA": "SI", "ESPANA": "ES", "ESTADOS UNIDOS": "US",
    "ESTONIA": "EE", "ETIOPIA": "ET", "FILIPINAS": "PH", "FINLANDIA": "FI",
    "FIYI": "FJ", "FRANCIA": "FR", "GABON": "GA", "GAMBIA": "GM",
    "GEORGIA": "GE", "GHANA": "GH", "GIBRALTAR": "GI", "GRANADA": "GD",
    "GRECIA": "GR", "GROENLANDIA": "GL", "GUADALUPE": "GP", "GUAM": "GU",
    "GUATEMALA": "GT", "GUAYANA FRANCESA": "GF", "GUINEA": "GN",
    "GUINEA ECUATORIAL": "GQ", "GUINEA-BISSAU": "GW", "GUYANA": "GY",
    "HAITI": "HT", "HONDURAS": "HN", "HONG KONG": "HK", "HUNGRIA": "HU",
    "INDIA": "IN", "INDONESIA": "ID", "IRAK": "IQ", "IRAN": "IR",
    "IRLANDA": "IE", "ISLA DE MAN": "IM", "ISLANDIA": "IS",
    "ISLAS CAIMAN": "KY", "ISLAS COOK": "CK", "ISLAS FEROE": "FO",
    "ISLAS MALVINAS": "FK", "ISLAS MARSHALL": "MH",
    "ISLAS SALOMON": "SB", "ISLAS TURCAS Y CAICOS": "TC",
    "ISLAS VIRGENES BRITANICAS": "VG",
    "ISLAS VIRGENES DE LOS ESTADOS UNIDOS": "VI", "ISRAEL": "IL",
    "ITALIA": "IT", "JAMAICA": "JM", "JAPON": "JP", "JORDANIA": "JO",
    "KENIA": "KE", "KIRGUISTAN": "KG", "KIRIBATI": "KI", "KUWAIT": "KW",
    "LAOS": "LA", "LESOTO": "LS", "LETONIA": "LV", "LIBANO": "LB",
    "LIBERIA": "LR", "LIBIA": "LY", "LIECHTENSTEIN": "LI",
    "LITUANIA": "LT", "LUXEMBURGO": "LU", "MACAO": "MO",
    "MACEDONIA DEL NORTE": "MK", "MADAGASCAR": "MG", "MALASIA": "MY",
    "MALAWI": "MW", "MALDIVAS": "MV", "MALI": "ML", "MALTA": "MT",
    "MARRUECOS": "MA", "MARTINICA": "MQ", "MAURICIO": "MU",
    "MAURITANIA": "MR", "MEXICO": "MX", "MICRONESIA": "FM",
    "MOLDAVIA": "MD", "MONACO": "MC", "MONGOLIA": "MN",
    "MONTENEGRO": "ME", "MONTSERRAT": "MS", "MOZAMBIQUE": "MZ",
    "MYANMAR (BIRMANIA)": "MM", "MYANMAR": "MM", "NAMIBIA": "NA",
    "NAURU": "NR", "NEPAL": "NP", "NICARAGUA": "NI", "NIGER": "NE",
    "NIGERIA": "NG", "NORUEGA": "NO", "NUEVA CALEDONIA": "NC",
    "NUEVA ZELANDA": "NZ", "OMAN": "OM", "PAISES BAJOS": "NL",
    "HOLANDA": "NL", "PAKISTAN": "PK", "PALAOS": "PW", "PALESTINA": "PS",
    "PANAMA": "PA", "PAPUA NUEVA GUINEA": "PG", "PARAGUAY": "PY",
    "PERU": "PE", "POLINESIA FRANCESA": "PF", "POLONIA": "PL",
    "PORTUGAL": "PT", "PUERTO RICO": "PR", "REINO UNIDO": "GB",
    "REPUBLICA CENTROAFRICANA": "CF", "REPUBLICA CHECA": "CZ",
    "REPUBLICA DEMOCRATICA DEL CONGO": "CD", "REPUBLICA DOMINICANA": "DO",
    "REPUBLICA DEL CONGO": "CG", "CONGO": "CG", "RUANDA": "RW",
    "RUMANIA": "RO", "RUSIA": "RU", "SAMOA": "WS",
    "SAMOA AMERICANA": "AS", "SAN CRISTOBAL Y NIEVES": "KN",
    "SAN MARINO": "SM", "SAN PEDRO Y MIQUELON": "PM",
    "SAN VICENTE Y LAS GRANADINAS": "VC", "SANTA LUCIA": "LC",
    "SANTO TOME Y PRINCIPE": "ST", "SENEGAL": "SN", "SERBIA": "RS",
    "SEYCHELLES": "SC", "SIERRA LEONA": "SL", "SINGAPUR": "SG",
    "SIRIA": "SY", "SOMALIA": "SO", "SRI LANKA": "LK",
    "SUDAFRICA": "ZA", "SUDAN": "SD", "SUDAN DEL SUR": "SS",
    "SUECIA": "SE", "SUIZA": "CH", "SURINAM": "SR", "SWAZILANDIA": "SZ",
    "ESUATINI": "SZ", "TAILANDIA": "TH", "TAIWAN": "TW",
    "TAYIKISTAN": "TJ", "TANZANIA": "TZ", "TIMOR ORIENTAL": "TL",
    "TOGO": "TG", "TONGA": "TO", "TRINIDAD Y TOBAGO": "TT",
    "TUNEZ": "TN", "TURKMENISTAN": "TM", "TURQUIA": "TR", "TUVALU": "TV",
    "UCRANIA": "UA", "UGANDA": "UG", "URUGUAY": "UY", "UZBEKISTAN": "UZ",
    "VANUATU": "VU", "VENEZUELA": "VE", "VIETNAM": "VN", "YEMEN": "YE",
    "YIBUTI": "DJ", "ZAMBIA": "ZM", "ZIMBABWE": "ZW",
    "NO RELACIONADO": "ZZ",

    # Alias detectados contra datos reales de la DIAN: usa nombres oficiales
    # largos (a veces con la forma "PAIS (REGION) ACLARACION") en vez de los
    # nombres cortos de uso común. Se agregan como claves adicionales al
    # mismo ISO2 (nunca se crea un país nuevo en el catálogo compartido
    # `Dimension.DimPais` por una variante de texto: ver Arquitectura.md).
    "ESTADOS UNIDOS DE AMERICA": "US",
    "REINO UNIDO DE GRAN BRETANA E IRLANDA DEL NORTE": "GB",
    "COREA (SUR) REPUBLICA DE": "KR",
    "COREA (NORTE) REPUBLICA POPULAR DEMOCRATICA DE": "KP",
    "IRAN REPUBLICA ISLAMICA DEL": "IR",
    "SIRIA, REPUBLICA ARABE DE": "SY",
    "VENEZUELA (REPUBLICA BOLIVARIANA DE)": "VE",
    "TANZANIA, REPUBLICA UNIDA DE": "TZ",
    "SUDAFRICA, REPUBLICA DE": "ZA",
    "LAO, REPUBLICA DEMOCRATICA POPULAR DE": "LA",
    "MICRONESIA, ESTADOS FEDERADOS DE": "FM",
    "MOLDOVA": "MD", "MOLDAVIA": "MD",
    "VIET NAM": "VN",
    "FEDERACION DE RUSIA": "RU",
    "IRLANDA (EIRE)": "IE",
    "PAISES BAJOS": "NL",
    "MYANMAR (BIRMANIA)": "MM",
    "TIMOR-LESTE": "TL",
    "MALVINAS, ISLAS": "FK",
    "MARSHALL, ISLAS": "MH",
    "COCOS (KEELING) ISLAS": "CC",
    "CAIMAN ISLAS": "KY", "CAIMAN, ISLAS": "KY",
    "TURCAS Y CAICOS, ISLAS": "TC",
    "VIRGENES ISLAS (BRITANICAS)": "VG",
    "VIRGENES ISLAS (ESTADOS UNIDOS)": "VI",
    "FEROE ISLAS": "FO", "FEROE, ISLAS": "FO",
    "ESTADO DE PALESTINA": "PS",
    "SAHARA OCCIDENTAL": "EH",
    "ESWATINI": "SZ",
    "KAZAJSTAN": "KZ", "UZBEKISTAN": "UZ", "TURKMENISTAN": "TM",
    "UCRANIA": "UA", "BELARUS": "BY",
    "NIUE": "NU", "DJIBOUTI": "DJ",
    "CAMBOYA (KAMPUCHEA)": "KH", "TOKELAU": "TK",
}


def resolver_iso2(nombre_pais) -> str | None:
    """Devuelve el ISO2 a partir del nombre de país tal como lo trae la DIAN
    (sin distinguir mayúsculas/acentos). None si no está en el catálogo (se
    deja para enriquecer manualmente después; no bloquea la carga)."""
    if not nombre_pais:
        return None
    return PAIS_A_ISO2.get(_normalizar(nombre_pais))


# Capítulos 01-97 del Sistema Armonizado (nomenclatura de la OMA), en
# español. Universal: no depende de ningún país del Data Warehouse.
CAPITULOS_HS = {
    "01": "Animales vivos",
    "02": "Carne y despojos comestibles",
    "03": "Pescados y crustáceos, moluscos y demás invertebrados acuáticos",
    "04": "Leche y productos lácteos; huevos de ave; miel natural",
    "05": "Los demás productos de origen animal",
    "06": "Plantas vivas y productos de la floricultura",
    "07": "Hortalizas, plantas, raíces y tubérculos alimenticios",
    "08": "Frutas y frutos comestibles; cortezas de agrios o de melones",
    "09": "Café, té, yerba mate y especias",
    "10": "Cereales",
    "11": "Productos de la molinería; malta; almidón y fécula; inulina; gluten de trigo",
    "12": "Semillas y frutos oleaginosos; semillas y frutos diversos; plantas industriales o medicinales",
    "13": "Gomas, resinas y demás jugos y extractos vegetales",
    "14": "Materias trenzables y demás productos de origen vegetal",
    "15": "Grasas y aceites animales o vegetales; grasas alimenticias elaboradas; ceras",
    "16": "Preparaciones de carne, pescado o de crustáceos, moluscos o demás invertebrados acuáticos",
    "17": "Azúcares y artículos de confitería",
    "18": "Cacao y sus preparaciones",
    "19": "Preparaciones a base de cereales, harina, almidón, fécula o leche; productos de pastelería",
    "20": "Preparaciones de hortalizas, frutas u otros frutos o demás partes de plantas",
    "21": "Preparaciones alimenticias diversas",
    "22": "Bebidas, líquidos alcohólicos y vinagre",
    "23": "Residuos y desperdicios de las industrias alimentarias; alimentos preparados para animales",
    "24": "Tabaco y sucedáneos del tabaco elaborados",
    "25": "Sal; azufre; tierras y piedras; yesos, cales y cementos",
    "26": "Minerales metalíferos, escorias y cenizas",
    "27": "Combustibles minerales, aceites minerales y productos de su destilación; materias bituminosas; ceras minerales",
    "28": "Productos químicos inorgánicos",
    "29": "Productos químicos orgánicos",
    "30": "Productos farmacéuticos",
    "31": "Abonos",
    "32": "Extractos curtientes o tintóreos; taninos y sus derivados; pigmentos; pinturas y barnices",
    "33": "Aceites esenciales y resinoides; preparaciones de perfumería, de tocador o de cosmética",
    "34": "Jabón, agentes de superficie orgánicos, preparaciones para lavar, preparaciones lubricantes, ceras artificiales",
    "35": "Materias albuminoideas; productos a base de almidón o de fécula modificados; colas; enzimas",
    "36": "Pólvoras y explosivos; artículos de pirotecnia; fósforos; aleaciones pirofóricas; materias inflamables",
    "37": "Productos fotográficos o cinematográficos",
    "38": "Productos diversos de las industrias químicas",
    "39": "Plástico y sus manufacturas",
    "40": "Caucho y sus manufacturas",
    "41": "Pieles (excepto la peletería) y cueros",
    "42": "Manufacturas de cuero; artículos de talabartería o guarnicionería; artículos de viaje, bolsos de mano",
    "43": "Peletería y confecciones de peletería; peletería facticia o artificial",
    "44": "Madera, carbón vegetal y manufacturas de madera",
    "45": "Corcho y sus manufacturas",
    "46": "Manufacturas de espartería o cestería",
    "47": "Pasta de madera o de las demás materias fibrosas celulósicas; papel o cartón para reciclar",
    "48": "Papel y cartón; manufacturas de pasta de celulosa, de papel o cartón",
    "49": "Productos editoriales, de la prensa y de las demás industrias gráficas",
    "50": "Seda",
    "51": "Lana y pelo fino u ordinario; hilados y tejidos de crin",
    "52": "Algodón",
    "53": "Las demás fibras textiles vegetales; hilados de papel y tejidos de hilados de papel",
    "54": "Filamentos sintéticos o artificiales; tiras y formas similares de materia textil sintética o artificial",
    "55": "Fibras sintéticas o artificiales discontinuas",
    "56": "Guata, fieltro y telas sin tejer; hilados especiales; cordeles, cuerdas y cordajes",
    "57": "Alfombras y demás revestimientos para el suelo, de materia textil",
    "58": "Tejidos especiales; superficies textiles con mechón insertado; encajes; tapicería",
    "59": "Telas impregnadas, recubiertas, revestidas o estratificadas; artículos técnicos de materia textil",
    "60": "Tejidos de punto",
    "61": "Prendas y complementos de vestir, de punto",
    "62": "Prendas y complementos de vestir, excepto los de punto",
    "63": "Los demás artículos textiles confeccionados",
    "64": "Calzado, polainas y artículos análogos; partes de estos artículos",
    "65": "Artículos de sombrerería y sus partes",
    "66": "Paraguas, sombrillas, quitasoles, bastones y artículos similares",
    "67": "Plumas y plumón preparados y artículos de plumas o plumón; flores artificiales; manufacturas de cabello",
    "68": "Manufacturas de piedra, yeso fraguable, cemento, amianto, mica o materias análogas",
    "69": "Productos cerámicos",
    "70": "Vidrio y sus manufacturas",
    "71": "Perlas finas, piedras preciosas, metales preciosos; bisutería; monedas",
    "72": "Fundición, hierro y acero",
    "73": "Manufacturas de fundición, hierro o acero",
    "74": "Cobre y sus manufacturas",
    "75": "Níquel y sus manufacturas",
    "76": "Aluminio y sus manufacturas",
    "78": "Plomo y sus manufacturas",
    "79": "Cinc y sus manufacturas",
    "80": "Estaño y sus manufacturas",
    "81": "Los demás metales comunes; cermets; manufacturas de estas materias",
    "82": "Herramientas y útiles, artículos de cuchillería, cubiertos de mesa, de metal común",
    "83": "Manufacturas diversas de metal común",
    "84": "Reactores nucleares, calderas, máquinas, aparatos y artefactos mecánicos",
    "85": "Máquinas, aparatos y material eléctrico y sus partes; aparatos de grabación o reproducción de sonido/imagen",
    "86": "Vehículos y material para vías férreas o similares; aparatos mecánicos de señalización para vías de comunicación",
    "87": "Vehículos automóviles, tractores, ciclos y demás vehículos terrestres",
    "88": "Aeronaves, vehículos espaciales, y sus partes",
    "89": "Barcos y demás artefactos flotantes",
    "90": "Instrumentos y aparatos de óptica, fotografía, cinematografía, medida, control o precisión; médico-quirúrgicos",
    "91": "Aparatos de relojería y sus partes",
    "92": "Instrumentos musicales; sus partes y accesorios",
    "93": "Armas y municiones; sus partes y accesorios",
    "94": "Muebles; mobiliario médico-quirúrgico; artículos de cama; aparatos de alumbrado no expresados en otra parte",
    "95": "Juguetes, juegos y artículos para recreo o deporte; sus partes y accesorios",
    "96": "Manufacturas diversas",
    "97": "Objetos de arte o colección y antigüedades",
}


def resolver_capitulo(codigo_subpartida: str):
    """(capitulo, nombre_capitulo) a partir de los 2 primeros dígitos del
    código de subpartida arancelaria. None si no viene un código válido."""
    if not codigo_subpartida or len(codigo_subpartida) < 2:
        return None, None
    capitulo = codigo_subpartida[:2]
    return capitulo, CAPITULOS_HS.get(capitulo)
