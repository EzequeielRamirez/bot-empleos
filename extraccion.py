"""Detecta si un post es una búsqueda laboral y extrae puesto, zona y contacto."""
import hashlib
import re
import unicodedata

DEPARTAMENTOS = [
    "Montevideo", "Canelones", "Maldonado", "Colonia", "San José", "Florida",
    "Durazno", "Flores", "Lavalleja", "Rocha", "Treinta y Tres", "Cerro Largo",
    "Rivera", "Artigas", "Salto", "Paysandú", "Río Negro", "Soriano", "Tacuarembó",
    "Punta del Este", "Ciudad de la Costa", "Las Piedras", "Pando", "Piriápolis",
]

# Formas explícitas ("Puesto: X") y frases típicas ("buscamos X", "llamado para X")
PATRON_EXPLICITO = r"(?:puesto|cargo|vacante|rol)\s*[:\-–]\s*([^\n.!¡?¿#:;]{3,70})"
PATRONES_PUESTO = [
    r"(?:oportunidad laboral|llamado(?: p[uú]blico)?|b[uú]squeda laboral)\s+(?:para|de)\s+"
    r"(?:el puesto de\s+)?(?:\d+\s+)?([^\n.,!¡?¿#:;(]{3,70})",
    r"(?:para el puesto de|en el puesto de|puesto de|cargo de)\s+([^\n.,!¡?¿#:;(]{3,70})",
    r"(?:estamos buscando|estamos sumando|estamos incorporando|buscamos|se busca|se buscan|"
    r"se necesita|se necesitan|necesitamos|se solicita|buscan|busca|est[aá] buscando|"
    r"en la b[uú]squeda de|incorporamos|seleccionamos|est[aá] seleccionando|"
    r"(?:busca|buscamos|queremos) (?:incorporar|sumar)|incorporar|sumar)\s+"
    r"(?:a\s+)?(?:(?:un|una|unos|unas|el|la|los|las)(?:\s*/\s*a|\(a\))?\s+)?"
    r"([^\n.,!¡?¿#:;(]{3,70})",
    r"(?:[aá]rea|sector) de\s+([^\n.,!¡?¿#:;(]{3,50})",
]
SEPARADORES = r"\s+[–—|]\s+|\s+-\s+|\s*\|\s*"
CORTES = (r"\s+(?:para|que|con experiencia|con o sin|zona|en el|en la|en zona|en nuestr[oa]s?|"
          r"a nuestro|a su|al equipo|y sumarte)\b")
GENERICOS_EXACTOS = {"personal", "talento", "gente", "personas", "equipo", "trabajo", "empleo"}
GENERICOS_INICIO = (
    "sumar", "personal para", "personal joven", "personal femenino", "personal masculino",
    "personal con", "personal idoneo", "talento", "gente", "personas", "nuevos", "nuevas",
    "colaborador", "integrante", "a nuestro", "busqueda laboral", "importante", "nueva vacante",
    "vacante", "oportunidad", "trabajo", "empleo", "urgente", "estamos", "te gusta", "buscamos",
    "se busca", "ingreso", "llamado", "atencion!", "atencion", "hola", "nueva", "nuevo",
    "sumate", "unite", "postulate", "incorporar", "enviar", "envia", "cv",
    "en ", "temporada", "busquedalaboral", "ofertalaboral", "seguimos", "somos",
)
VERBOS_DE_FRASE = re.compile(r"busc|selecci|abre|necesit|sumamos|incorpor|tenemos|queremos|"
                             r"envi|postul|\bcv\b|seguimos|crecie|\?",
                             re.IGNORECASE)

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def normalizar(texto):
    texto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def limpiar(texto):
    """Quita emojis y símbolos raros, deja letras, números y puntuación básica."""
    permitido = []
    for c in texto:
        cat = unicodedata.category(c)
        if cat[0] in "LNZ" or c in "/-&+()'\"":
            permitido.append(c)
        else:
            permitido.append(" ")
    return re.sub(r"\s+", " ", "".join(permitido)).strip(" -/")


SENALES_DE_POSTULACION = ("cv", "curriculum", "postul", "envia", "enviar", "whatsapp", "wsp",
                          "mensaje privado", "privado", "inscrib", "formulario", "link",
                          "interesad", "comunicarse", "contacto", "llamar", "dm")


def es_busqueda_laboral(caption, config):
    if not caption or len(caption) < config["minimo_caracteres_descripcion"]:
        return False
    t = normalizar(caption)
    if any(p in t for p in config["palabras_prohibidas"]):
        return False
    # Solo Uruguay: los hashtags en español traen ofertas de otros países
    if any(re.search(r"(?<![a-z])" + re.escape(p) + r"(?![a-z])", t)
           for p in config.get("palabras_de_otros_paises", [])):
        return False
    if not any(p in t for p in config["palabras_de_busqueda_laboral"]):
        return False
    # Tiene que decir cómo postularse (descarta noticias y consejos)
    return bool(EMAIL.search(caption)) or any(s in t for s in SENALES_DE_POSTULACION)


def huella(caption):
    """Identifica la misma oferta aunque la hayan subido varias cuentas."""
    base = re.sub(r"[^a-z0-9]", "", normalizar(caption))[:250]
    return hashlib.sha1(base.encode()).hexdigest()[:16]


def _candidato(texto):
    """Limpia un posible puesto; devuelve None si es genérico."""
    texto = re.split(SEPARADORES, texto, maxsplit=1)[0]
    texto = limpiar(texto).strip(" !¡")
    texto = re.split(CORTES, texto, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    if len(texto) > 45:
        texto = texto[:45].rsplit(" ", 1)[0]
    # No terminar en "de", "por", "en"…
    texto = re.sub(r"(?:\s+(?:de|del|en|por|para|y|con|la|el|los|las|a))+$", "", texto, flags=re.IGNORECASE)
    n = normalizar(texto)
    if (len(texto) < 3 or n in GENERICOS_EXACTOS or n.startswith(GENERICOS_INICIO)
            or re.match(r"\d+\s+(?:vacantes|puestos|personas)", n)):
        return None
    return texto


def _desde_titulo(caption):
    """Muchos posts arrancan con "🍔 Cajero/a – Empresa" o "BÚSQUEDA LABORAL | ASISTENTE"."""
    primera = next((l for l in caption.splitlines() if limpiar(l)), "")
    for parte in re.split(SEPARADORES, primera)[:2]:
        if VERBOS_DE_FRASE.search(parte) or len(limpiar(parte)) > 60:
            continue
        candidato = _candidato(parte)
        if candidato:
            return candidato
    return None


def extraer_puesto(caption):
    m = re.search(PATRON_EXPLICITO, caption, re.IGNORECASE)
    if m and _candidato(m.group(1)):
        return _candidato(m.group(1))
    titulo = _desde_titulo(caption)
    if titulo:
        return titulo
    for patron in PATRONES_PUESTO:
        for m in re.finditer(patron, caption, re.IGNORECASE):
            candidato = _candidato(m.group(1))
            if candidato:
                return candidato
    return "Personal"


def extraer_zona(caption):
    t = normalizar(caption)
    for lugar in DEPARTAMENTOS:
        if re.search(r"\b" + re.escape(normalizar(lugar)) + r"\b", t):
            return lugar
    return "Uruguay"


def extraer_email(caption):
    m = EMAIL.search(caption)
    return m.group(0).rstrip(".") if m else None


def descripcion_sin_hashtags(caption, limite=900):
    texto = re.sub(r"(?:^|\s)#\w+", "", caption).strip()
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    if len(texto) > limite:
        texto = texto[:limite].rsplit(" ", 1)[0] + "…"
    return texto


# ---------------------------------------------------------------- contacto

TELEFONO = re.compile(r"(?<![\d$.,])(?:\+?\s?598[\s.-]?)?\(?0?\d{1,2}\)?[\s.-]?\d{3}[\s.-]?\d{3,4}(?![\d])")
PALABRA_WHATSAPP = re.compile(r"whats\s?app|wpp|wsp|whats|wapp", re.IGNORECASE)


def _numero_uy(texto):
    """Devuelve el número uruguayo en 8 dígitos (sin 0 ni 598) o None."""
    d = re.sub(r"\D", "", texto)
    if d.startswith("598"):
        d = d[3:]
    d = d.lstrip("0")
    return d if len(d) == 8 and d[0] in "2349" else None


def formato_local(numero):
    if numero.startswith("9"):  # celular: 099 123 456
        return f"0{numero[:2]} {numero[2:5]} {numero[5:]}"
    return f"{numero[:4]} {numero[4:]}"


def extraer_contacto(caption):
    """Email, WhatsApp y teléfono fijo. El WhatsApp es el número que aparece junto a la
    palabra "WhatsApp" o, si no, el primer celular uruguayo (09X)."""
    whatsapp = telefono = None
    m = re.search(r"wa\.me/(\d+)", caption)
    if m:
        whatsapp = _numero_uy(m.group(1))
    if not whatsapp:
        for palabra in PALABRA_WHATSAPP.finditer(caption):
            for n in TELEFONO.finditer(caption, palabra.end(), palabra.end() + 45):
                whatsapp = _numero_uy(n.group())
                if whatsapp:
                    break
            if whatsapp:
                break
    for n in TELEFONO.finditer(caption):
        numero = _numero_uy(n.group())
        if not numero or numero == whatsapp:
            continue
        if numero.startswith("9") and not whatsapp:
            whatsapp = numero
        elif not numero.startswith("9") and not telefono:
            telefono = numero
    return {"email": extraer_email(caption), "whatsapp": whatsapp, "telefono": telefono}


# ---------------------------------------------------------------- rubro

RUBROS = [
    ("Gastronomía", ["cocin", "chef", "mozo", "moza", "barista", "gastronom", "panader", "pizz",
                     "cafeter", "bacher", "parriller", "restaurant", "pasteler", "carro de comida"]),
    ("Ventas y atención al público", ["vendedor", "ventas", "cajer", "atencion al cliente",
                                      "atencion al publico", "comercial", "promotor", "tienda",
                                      "call center", "telemarket", "repositor"]),
    ("Limpieza y mantenimiento", ["limpieza", "limpiador", "mucama", "mantenimiento", "conserje",
                                  "portero", "jardiner"]),
    ("Salud y cuidados", ["cuidador", "enfermer", "medic", "acompanante", "adultos mayores",
                          "odontolog", "farmac", "psicolog", "ninera", "diagnostico", "salud",
                          "social", "trabajador/a social"]),
    ("Administración y oficina", ["administrativ", "contable", "contador", "auditor", "recepcionista",
                                  "secretari", "rrhh", "recursos humanos", "siniestros", "oficina",
                                  "data entry", "facturacion", "cobranza"]),
    ("Logística y transporte", ["chofer", "repartidor", "reparto", "logistic", "deposito",
                                "expedicion", "conductor", "cadete", "camion", "delivery"]),
    ("Construcción y oficios", ["obra", "construccion", "albanil", "electricista", "sanitario",
                                "pintor", "carpinter", "herrer", "soldador", "mecanic", "tecnico de obra",
                                "tecnico electric", "tecnico en mantenimiento"]),
    ("Industria y producción", ["operario", "fabrica", "produccion", "planta", "industrial",
                                "frigorifico", "envasado"]),
    ("Tecnología y marketing", ["programador", "desarrollador", "developer", "sistemas", "informatic",
                                "community manager", "marketing", "disenador", "redes sociales",
                                "tiktok", "contenido digital"]),
    ("Educación", ["docente", "maestr", "profesor", "educador", "tutor"]),
    ("Belleza y estética", ["peluquer", "lashista", "manicur", "estetic", "barber", "cosmetolog",
                            "maquillador", "pestan"]),
    ("Seguridad", ["guardia", "seguridad", "vigilante", "custodia"]),
    ("Turismo y eventos", ["animador", "recreac", "eventos", "hotel", "turismo"]),
]


def extraer_rubro(puesto, caption):
    """Primero mira el puesto; si no alcanza, el texto completo."""
    for texto in (normalizar(puesto), normalizar(caption)):
        for rubro, palabras in RUBROS:
            if any(p in texto for p in palabras):
                return rubro
    return "Otros rubros"
