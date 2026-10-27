"""Empresas que están publicando búsquedas laborales → lista diaria para ofrecerles la publicidad
de BTU y TCM, con el mensaje personalizado y botones de un clic (WhatsApp, email, Instagram).

El envío lo hace una persona: Instagram no permite que un programa mande el primer mensaje, y los
mensajes masivos automáticos hacen que bloqueen las cuentas (y en WhatsApp, el número).
"""
import re
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

from extraccion import (es_busqueda_laboral, extraer_contacto, extraer_puesto, extraer_rubro,
                        formato_local, normalizar)
from ubicacion import SENALES_URUGUAY, extraer_ubicacion

CARPETA = Path(__file__).parent / "prospectos"


def es_prospecto(caption, config):
    """Empresa de Uruguay buscando personal. A diferencia de las ofertas que se publican, acá no
    hace falta que el texto traiga contacto: se les puede escribir por Instagram."""
    if not es_busqueda_laboral(caption, config):
        return False
    t = normalizar(caption)
    if any(re.search(r"(?<![a-z])" + re.escape(p) + r"(?![a-z])", t)
           for p in config.get("palabras_de_otros_paises", [])):
        return False
    return extraer_ubicacion(caption) is not None or bool(SENALES_URUGUAY.search(caption))


def clave_empresa(caption, permalink):
    """La misma empresa (mismo WhatsApp, email o web) no se contacta dos veces."""
    c = extraer_contacto(caption)
    if c.get("whatsapp"):
        return "wa:" + c["whatsapp"]
    if c.get("telefono"):
        return "tel:" + c["telefono"]
    if c.get("email"):
        dominio = c["email"].split("@")[-1].lower()
        genericos = ("gmail.com", "hotmail.com", "outlook.com", "yahoo.com", "adinet.com.uy", "live.com")
        return "mail:" + (c["email"].lower() if dominio in genericos else dominio)
    if c.get("web"):
        return "web:" + c["web"].lower().split("/")[0].removeprefix("www.")
    return "ig:" + permalink


def nuevo(post_id, caption, permalink, fecha):
    puesto = extraer_puesto(caption)
    return {"id": post_id, "caption": caption, "permalink": permalink, "timestamp": fecha,
            "clave": clave_empresa(caption, permalink), "puesto": puesto,
            "zona": extraer_ubicacion(caption) or "", "rubro": extraer_rubro(puesto, caption)}


def _datos_mensaje(p):
    puesto = p["puesto"]
    puesto_txt = puesto.lower() if puesto.isupper() else puesto[0].lower() + puesto[1:]  # "AUXILIAR" → "auxiliar"
    zona_txt = f" en {p['zona']}" if p.get("zona") else ""
    return {"puesto": puesto_txt, "zona": zona_txt}


def mensaje(p, config):
    return config["mensaje_prospectos"].format(**_datos_mensaje(p)).strip()


def asunto(p, config):
    return config["asunto_email_prospectos"].format(**_datos_mensaje(p)).strip()


def _sin_formato(texto):
    return texto.replace("*", "")


def puntaje(p):
    """Primero las que se pueden contactar directo y las más recientes."""
    c = extraer_contacto(p["caption"])
    s = 3 if c.get("whatsapp") else 2 if c.get("email") else 1 if (c.get("telefono") or c.get("web")) else 0
    return (s, p["timestamp"])


def generar_reporte(estado, config, hoy):
    """Elige hasta N empresas no contactadas, arma prospectos/<fecha>.md y las marca como contactadas."""
    cantidad = config.get("prospectos_por_dia", 40)
    olvidar = (datetime.fromisoformat(hoy) - timedelta(days=config.get("dias_para_volver_a_contactar", 60))).date().isoformat()
    contactados = {k: v for k, v in estado.get("contactados", {}).items() if v >= olvidar}
    pendientes = [p for p in estado.get("prospectos", []) if p["clave"] not in contactados]
    pendientes.sort(key=puntaje, reverse=True)
    elegidos, claves = [], set()
    for p in pendientes:
        if p["clave"] in claves:
            continue
        claves.add(p["clave"])
        elegidos.append(p)
        if len(elegidos) >= cantidad:
            break

    lineas = [f"# Empresas para contactar — {hoy}", "",
              f"**{len(elegidos)} empresas** que están buscando personal en Uruguay. "
              "Cada una tiene su mensaje listo: tocá el botón, revisá y enviá.", "",
              "- **WhatsApp / Email:** se abre con el texto ya escrito.",
              "- **Instagram:** abrí la publicación → entrá al perfil de la empresa → *Mensaje* → pegá el texto "
              "(botón de copiar arriba a la derecha del recuadro).",
              "- Enviá de a poco (no todos seguidos) para que Instagram/WhatsApp no lo tome como spam.", ""]
    for i, p in enumerate(elegidos, 1):
        c = extraer_contacto(p["caption"])
        texto = mensaje(p, config)
        botones = []
        if c.get("whatsapp"):
            botones.append(f"[📲 WhatsApp {formato_local(c['whatsapp'])}](https://wa.me/598{c['whatsapp']}"
                           f"?text={urllib.parse.quote(texto)})")
        if c.get("email"):
            botones.append(f"[📩 Email {c['email']}](mailto:{c['email']}?subject="
                           f"{urllib.parse.quote(asunto(p, config))}&body={urllib.parse.quote(_sin_formato(texto))})")
        if c.get("telefono"):
            botones.append(f"📞 {formato_local(c['telefono'])}")
        if c.get("web"):
            botones.append(f"🌐 {c['web']}")
        botones.append(f"[📷 Ver publicación en Instagram]({p['permalink']})")
        dias = (datetime.fromisoformat(hoy) - datetime.strptime(p["timestamp"][:10], "%Y-%m-%d")).days
        lineas += [f"## {i}. {p['puesto']}" + (f" — {p['zona']}" if p.get("zona") else ""),
                   f"{p['rubro']} · publicada hace {dias} día{'s' if dias != 1 else ''}", "",
                   " · ".join(botones), "", "```text", texto, "```", ""]
        contactados[p["clave"]] = hoy

    estado["contactados"] = contactados
    usados = {p["clave"] for p in elegidos}
    estado["prospectos"] = [p for p in pendientes if p["clave"] not in usados][:500]
    CARPETA.mkdir(exist_ok=True)
    ruta = CARPETA / f"{hoy}.md"
    contenido = "\n".join(lineas) + "\n"
    ruta.write_text(contenido, encoding="utf-8")
    (CARPETA / "HOY.md").write_text(contenido, encoding="utf-8")
    return ruta, len(elegidos)
