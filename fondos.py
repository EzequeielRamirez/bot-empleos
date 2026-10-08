"""Fondo de foto según el oficio. Las fotos están en assets/fondos/ (generadas una sola vez,
gratis, con herramientas/generar_fondos.py)."""
from pathlib import Path

from extraccion import normalizar

CARPETA = Path(__file__).parent / "assets" / "fondos"

# archivo → (palabras clave del puesto, descripción para generar la foto)
OFICIOS = {
    "jardinero": (["jardiner", "parquista", "paisajis"], "a gardener trimming green hedges in a sunny garden"),
    "repartidor": (["repartidor", "delivery", "cadete", "motoquero", "mensajer"],
                   "a delivery rider on a motorcycle with a delivery box on a city street"),
    "chofer": (["chofer", "conductor", "camion", "libreta", "transport"],
               "a professional truck driver smiling inside the cab of a delivery truck"),
    "cocinero": (["cocin", "chef", "parriller", "pizz", "bacher", "minutas"],
                 "a chef cooking in a busy professional restaurant kitchen with flames"),
    "mozo": (["mozo", "moza", "camarer", "mesero", "salonero"],
             "a waiter in an apron serving plates at a cozy restaurant"),
    "barista": (["barista", "cafeter"], "a barista preparing latte art in a modern coffee shop"),
    "panadero": (["panader", "pasteler", "confiter", "reposter"],
                 "a baker taking fresh bread out of an oven in a bakery"),
    "cajero": (["cajer"], "a cashier smiling at the checkout counter of a supermarket"),
    "supermercado": (["repositor", "supermercado", "fiambreria", "carniceria", "almacen"],
                     "a supermarket employee stocking shelves with products"),
    "vendedor": (["vendedor", "ventas", "comercial", "promotor", "tienda", "showroom"],
                 "a sales assistant showing a jacket to a customer between clothing racks in a bright retail store, wide shot"),
    "call_center": (["call center", "telemarket", "telefonic", "atencion al cliente", "contact center"],
                    "a customer service agent with a headset working in a modern call center"),
    "limpieza": (["limpieza", "limpiador", "mucama", "aseo"],
                 "a cleaning professional mopping the floor of a bright modern office"),
    "cuidador": (["cuidador", "acompanante", "adultos mayores", "residencial", "geriatr"],
                 "a caregiver helping an elderly woman in a warm living room"),
    "enfermero": (["enfermer", "auxiliar de enfermeria", "salud"],
                  "a nurse in scrubs in a bright hospital corridor"),
    "medico": (["medic", "doctor", "odontolog", "diagnostico", "farmac", "laboratorio"],
               "a doctor in a white coat with a stethoscope in a modern clinic"),
    "administrativo": (["administrativ", "contable", "contador", "auditor", "secretari", "data entry",
                        "facturacion", "siniestros", "seguros", "ejecutivo", "oficina", "cobranza", "rrhh"],
                       "an office worker at a desk with a laptop in a modern bright office"),
    "recepcionista": (["recepcion"], "a receptionist smiling behind the front desk of a modern lobby"),
    "operario": (["operario", "fabrica", "produccion", "planta", "industrial", "envasado", "frigorifico"],
                 "a factory worker with safety helmet operating machinery in an industrial plant"),
    "deposito": (["deposito", "expedicion", "logistic", "almacenamiento", "picking", "autoelevador"],
                 "a warehouse worker moving boxes with a pallet jack in a large warehouse"),
    "albanil": (["albanil", "obra", "construccion", "peon", "oficial de obra"],
                "a construction worker with a hard hat building a brick wall at a construction site"),
    "electricista": (["electricista", "electric"], "an electrician working on an electrical panel"),
    "mecanico": (["mecanic", "taller", "gomeria", "chapista"],
                 "a mechanic repairing a car engine in an auto repair shop"),
    "tecnico": (["tecnico", "mantenimiento", "sanitario", "instalador", "aire acondicionado"],
                "a maintenance technician with tools repairing equipment"),
    "guardia": (["guardia", "seguridad", "vigilante", "custodia", "sereno"],
                "a security guard in uniform standing at the entrance of a building"),
    "peluquero": (["peluquer", "barber", "estilista", "colorista"],
                  "a hairdresser in a black apron cutting a seated client's hair with scissors and comb in a modern hair salon, mirrors, wide shot"),
    "estetica": (["lashista", "manicur", "estetic", "cosmetolog", "pestan", "unas", "maquillador", "masajista"],
                 "close-up of hands of a manicurist painting a client's nails at a nail salon table with polish bottles"),
    "docente": (["docente", "maestr", "profesor", "educador", "tutor", "educacion"],
                "a teacher writing on a whiteboard in front of a classroom full of students raising hands, view from the back of the class"),
    "ninera": (["ninera", "nana", "babysitter", "jardin de infantes"],
               "an adult nanny sitting on the floor building wooden blocks with a toddler in a bright playroom, wide shot"),
    "animador": (["animador", "recreac", "eventos", "fiesta"],
                 "an adult entertainer in a colorful costume performing for a group of laughing children at a birthday party, wide shot"),
    "hotel": (["hotel", "turismo", "hosteria", "camarista"],
              "a hotel staff member at the reception of an elegant hotel"),
    "programador": (["programador", "desarrollador", "developer", "sistemas", "informatic", "software", "soporte it"],
                    "a software developer coding on two monitors in a modern office"),
    "marketing": (["community manager", "marketing", "redes sociales", "disenador", "contenido", "tiktok"],
                  "a content creator filming a product with a smartphone on a tripod with a ring light in a small studio, wide shot"),
    "social": (["social", "psicolog", "comunitari"],
               "a social worker holding a clipboard talking with a group of adults sitting in a circle at a community center, wide shot"),
    "generico": ([], "a diverse team of workers smiling together in a modern workplace"),
}

POR_RUBRO = {
    "Gastronomía": "cocinero", "Ventas y atención al público": "vendedor",
    "Limpieza y mantenimiento": "limpieza", "Salud y cuidados": "cuidador",
    "Administración y oficina": "administrativo", "Logística y transporte": "deposito",
    "Construcción y oficios": "albanil", "Industria y producción": "operario",
    "Tecnología y marketing": "programador", "Educación": "docente",
    "Belleza y estética": "estetica", "Seguridad": "guardia", "Turismo y eventos": "animador",
}


def elegir_fondo(puesto, rubro, caption=""):
    """Primero por el puesto, después por el texto, y si no, por el rubro."""
    for texto in (normalizar(puesto), normalizar(caption)[:400]):
        for archivo, (palabras, _) in OFICIOS.items():
            if any(p in texto for p in palabras):
                ruta = CARPETA / f"{archivo}.jpg"
                if ruta.exists():
                    return ruta
    ruta = CARPETA / f"{POR_RUBRO.get(rubro, 'generico')}.jpg"
    return ruta if ruta.exists() else (CARPETA / "generico.jpg" if (CARPETA / "generico.jpg").exists() else None)
