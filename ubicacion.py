"""Ubicación precisa dentro de Uruguay: barrio o ciudad + departamento.

Una oferta solo se acepta si nombra un lugar de Uruguay. Los nombres que también existen en
Argentina u otros países (Palermo, Flores, Salto, Mercedes, Rosario…) o que son palabras comunes
(Colonia, Florida, Durazno, Centro…) solo cuentan si el texto tiene además una señal clara de
Uruguay (un teléfono uruguayo, ".uy", "Montevideo", un organismo uruguayo, etc.).
"""
import re

from extraccion import normalizar

DEPARTAMENTOS = {
    "Montevideo", "Canelones", "Maldonado", "Colonia", "San José", "Florida", "Durazno", "Flores",
    "Lavalleja", "Rocha", "Treinta y Tres", "Cerro Largo", "Rivera", "Artigas", "Salto", "Paysandú",
    "Río Negro", "Soriano", "Tacuarembó",
}

# lugar → departamento
LUGARES = {
    # Barrios de Montevideo
    **{b: "Montevideo" for b in [
        "Pocitos", "Punta Carretas", "Carrasco", "Malvín", "Malvín Norte", "Buceo", "Punta Gorda",
        "Cordón", "Tres Cruces", "La Blanqueada", "Parque Batlle", "Parque Rodó", "Ciudad Vieja",
        "Barrio Sur", "Palermo", "Aguada", "Goes", "Reducto", "Jacinto Vera", "La Comercial",
        "Larrañaga", "Brazo Oriental", "Prado", "Capurro", "Bella Vista", "Belvedere", "Nuevo París",
        "La Teja", "Paso Molino", "Cerro", "Casabó", "Paso de la Arena", "Sayago", "Peñarol", "Colón",
        "Lezica", "Conciliación", "Manga", "Piedras Blancas", "Casavalle", "Unión", "Maroñas",
        "Flor de Maroñas", "Villa Española", "Ituzaingó", "Las Acacias", "Cerrito", "Atahualpa",
        "Villa Muñoz", "Mercado Modelo", "Bañados de Carrasco", "Punta de Rieles", "Villa García",
        "Carrasco Norte", "Parque Rodó", "Centro", "Tres Ombúes", "Nuevo Centro", "Villa Dolores",
    ]},
    # Canelones
    **{c: "Canelones" for c in [
        "Las Piedras", "La Paz", "Progreso", "Santa Lucía", "Pando", "Barros Blancos", "Toledo",
        "Joaquín Suárez", "Sauce", "Atlántida", "Parque del Plata", "Salinas", "Ciudad de la Costa",
        "Solymar", "Lagomar", "Shangrilá", "El Pinar", "Paso Carrasco", "Colonia Nicolich", "Tala",
        "San Ramón", "Empalme Olmos", "Suárez", "Neptunia", "La Floresta", "San Jacinto", "Migues",
        "Santa Rosa", "Juanicó", "Los Cerrillos", "Aeropuerto de Carrasco", "Zonamerica", "Zonamérica",
    ]},
    # Maldonado
    **{c: "Maldonado" for c in [
        "Punta del Este", "San Carlos", "Piriápolis", "Pan de Azúcar", "Aiguá", "La Barra",
        "José Ignacio", "Manantiales", "Punta Ballena", "Solanas", "Portezuelo", "Cerro Pelado",
    ]},
    # Colonia
    **{c: "Colonia" for c in [
        "Colonia del Sacramento", "Carmelo", "Nueva Helvecia", "Rosario", "Juan Lacaze",
        "Nueva Palmira", "Tarariras", "Ombúes de Lavalle", "Colonia Valdense",
    ]},
    # San José
    **{c: "San José" for c in ["San José de Mayo", "Ciudad del Plata", "Libertad", "Rodríguez",
                               "Ecilda Paullier", "Delta del Tigre", "Playa Pascual"]},
    # Resto del interior
    "Minas": "Lavalleja", "José Pedro Varela": "Lavalleja",
    "Trinidad": "Flores",
    "La Paloma": "Rocha", "Chuy": "Rocha", "Castillos": "Rocha", "Lascano": "Rocha",
    "Punta del Diablo": "Rocha", "Cabo Polonio": "Rocha",
    "Melo": "Cerro Largo", "Río Branco": "Cerro Largo",
    "Bella Unión": "Artigas",
    "Fray Bentos": "Río Negro", "Young": "Río Negro",
    "Mercedes": "Soriano", "Dolores": "Soriano", "Cardona": "Soriano",
    "Paso de los Toros": "Tacuarembó",
    "Sarandí del Yí": "Durazno",
    "Sarandí Grande": "Florida",
    "Vergara": "Treinta y Tres",
    "Nueva Palmira": "Colonia",
    "Constitución": "Salto",
    "Guichón": "Paysandú",
}

# Nombres que existen en otros países o son palabras comunes: necesitan otra señal de Uruguay
AMBIGUOS = {normalizar(n) for n in [
    "Colonia", "Florida", "Durazno", "Flores", "Rocha", "Rivera", "Artigas", "Salto", "San José",
    "Río Negro", "Palermo", "Centro", "Cordón", "Prado", "Unión", "Cerro", "Manga", "Aguada",
    "Belvedere", "Colón", "La Paz", "Progreso", "Sauce", "Tala", "Toledo", "Suárez", "Rosario",
    "Libertad", "Rodríguez", "Mercedes", "Dolores", "Minas", "Young", "Trinidad", "Constitución",
    "Carrasco", "Santa Rosa", "Santa Lucía", "Vergara", "Cardona", "Las Acacias", "Bella Vista",
    "La Barra", "Lezica", "Conciliación", "Nuevo Centro", "Villa Dolores", "Cerrito", "Atahualpa",
    "Mercado Modelo", "Ituzaingó", "Villa García", "Salinas", "Castillos", "Melo", "La Comercial",
    "Goes", "Reducto", "Capurro", "San Carlos", "Pando", "Las Piedras", "Atlántida", "Punta Gorda",
]}

SENALES_URUGUAY = re.compile(
    r"uruguay|montevide|\+\s?598|\b09\d[\s.-]?\d{3}[\s.-]?\d{3}\b|"
    r"(?<!11 )(?<!11-)(?<!\) )\b[24]\d{3}[\s.-]?\d{4}\b|\.uy\b|"  # fijos de UY (no los 11 de Bs. As.)
    r"\b(?:utu|bps|mides|imm|intendencia de|ancap|antel|ute|ose|asse|udelar|inau|dgi)\b",
    re.IGNORECASE)

_ORDEN = sorted(set(LUGARES) | DEPARTAMENTOS, key=len, reverse=True)  # "Malvín Norte" antes que "Malvín"


def extraer_ubicacion(caption):
    """Devuelve "Barrio o ciudad, Departamento", solo "Departamento", o None si no hay un lugar
    de Uruguay confiable."""
    t = normalizar(caption)
    hay_senal = bool(SENALES_URUGUAY.search(caption))
    encontrados = []
    for nombre in _ORDEN:
        n = normalizar(nombre)
        m = re.search(r"(?<![a-z])" + re.escape(n) + r"(?![a-z])", t)
        if not m or any(m.start() >= a and m.end() <= b for a, b, _ in encontrados):
            continue  # ya cubierto por un nombre más largo ("Ciudad de la Costa" ⊃ "Costa")
        if n in AMBIGUOS and not hay_senal:
            continue
        encontrados.append((m.start(), m.end(), nombre))
    if not encontrados:
        return None
    encontrados.sort()
    # Lo más específico primero: un barrio o ciudad gana sobre el departamento
    especificos = [n for _, _, n in encontrados if n in LUGARES and LUGARES[n] != n]
    if especificos:
        lugar = especificos[0]
        return f"{lugar}, {LUGARES[lugar]}"
    return encontrados[0][2]


# ---------------------------------------------------------------- ubicación de la publicación

import json as _json
from pathlib import Path as _Path

_CODIGOS = {k: v for k, v in _json.loads(
    (_Path(__file__).parent / "assets" / "ubicaciones_instagram.json").read_text(encoding="utf-8")).items()
    if not k.startswith("_")}


def codigo_ubicacion(zona):
    """'Pocitos, Montevideo' → código de Pocitos; si no está, el del departamento; si no, None."""
    if not zona:
        return None
    for parte in [p.strip() for p in zona.split(",")]:  # primero el barrio/ciudad, después el departamento
        if parte in _CODIGOS:
            return _CODIGOS[parte]
    return None
