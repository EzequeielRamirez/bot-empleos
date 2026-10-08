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

PATRONES_PUESTO = [
    r"(?:puesto|cargo|vacante|rol)\s*[:\-–]\s*([^\n.!¡?¿#:;|]{3,70})",
    r"(?:estamos buscando|buscamos|se busca|se necesita|necesitamos|se solicita|"
    r"estamos en la b[uú]squeda de|incorporamos|seleccionamos)\s+"
    r"(?:a\s+)?(?:(?:un|una|unos|unas|el|la)(?:\s*/\s*a|\(a\))?\s+)?"
    r"([^\n.,!¡?¿#:;(|]{3,70})",
]

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


def es_busqueda_laboral(caption, config):
    if not caption or len(caption) < config["minimo_caracteres_descripcion"]:
        return False
    t = normalizar(caption)
    if any(p in t for p in config["palabras_prohibidas"]):
        return False
    return any(p in t for p in config["palabras_de_busqueda_laboral"])


def huella(caption):
    """Identifica la misma oferta aunque la hayan subido varias cuentas."""
    base = re.sub(r"[^a-z0-9]", "", normalizar(caption))[:250]
    return hashlib.sha1(base.encode()).hexdigest()[:16]


def extraer_puesto(caption):
    for patron in PATRONES_PUESTO:
        m = re.search(patron, caption, re.IGNORECASE)
        if m:
            puesto = limpiar(m.group(1))
            # Cortamos en conectores que suelen iniciar otra idea
            puesto = re.split(r"\s+(?:para trabajar|que |con experiencia|zona|en el|en la|en zona)\b",
                              puesto, maxsplit=1, flags=re.IGNORECASE)[0]
            if len(puesto) > 45:
                puesto = puesto[:45].rsplit(" ", 1)[0]
            if len(puesto) >= 3:
                return puesto
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
