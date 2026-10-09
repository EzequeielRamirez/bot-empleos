"""Busca búsquedas laborales recientes en Instagram (por hashtags) y publica
una tarjeta propia en cada cuenta configurada.

Uso:
  python bot.py                 # busca y publica (lo que corre cada hora en GitHub)
  python bot.py --sin-publicar  # busca y genera las tarjetas, pero no publica
  python bot.py --prueba        # sin internet: genera tarjetas, historias y reels de ejemplo
  python bot.py --configurar    # muestra los IDs de tus cuentas de Instagram
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from extraccion import (descripcion_sin_hashtags, es_busqueda_laboral, extraer_contacto,
                        extraer_puesto, extraer_rubro, formato_local, huella)
from ubicacion import extraer_ubicacion
from fondos import elegir_fondo
from tarjeta import generar_tarjeta, generar_vertical
from video import generar_video

RAIZ = Path(__file__).parent
ARCHIVO_ESTADO = RAIZ / "estado.json"
CARPETA_SALIDA = RAIZ / "salida"
RAMA_IMAGENES = "imagenes"
MAX_HISTORIAL = 5000
AVISO = ("⚠️ Importante: {marca} no contrata, no selecciona personal y no recibe currículums. "
         "Únicamente difundimos oportunidades laborales publicadas por empresas y terceros. "
         "La postulación debe realizarse directamente mediante el contacto indicado.")


def oferta_valida(caption, config):
    """Búsqueda laboral + un lugar de Uruguay identificable (si no, puede ser de otro país)."""
    return es_busqueda_laboral(caption, config) and extraer_ubicacion(caption) is not None


class ErrorGraph(Exception):
    pass


class Graph:
    def __init__(self, token, version):
        import requests
        self.http = requests.Session()
        self.token = token
        self.base = f"https://graph.facebook.com/{version}"

    def _respuesta(self, r):
        data = r.json()
        if "error" in data:
            raise ErrorGraph(data["error"].get("message", str(data["error"])))
        return data

    def get(self, ruta, **params):
        params["access_token"] = self.token
        return self._respuesta(self.http.get(f"{self.base}/{ruta}", params=params, timeout=60))

    def post(self, ruta, **params):
        params["access_token"] = self.token
        return self._respuesta(self.http.post(f"{self.base}/{ruta}", data=params, timeout=60))


def ahora():
    return datetime.now(timezone.utc)


def cargar_json(ruta, defecto):
    if ruta.exists():
        return json.loads(ruta.read_text(encoding="utf-8"))
    return defecto


def estado_inicial():
    return {"hashtag_ids": {}, "vistos": [], "huellas": [], "cola": [], "publicados": []}


def git(*args):
    subprocess.run(["git", *args], cwd=RAIZ, check=True)


# ---------------------------------------------------------------- búsqueda

def buscar_ofertas(api, ig_id, config, estado, tipo="recent_media"):
    """tipo: "recent_media" (últimas 24 h) o "top_media" (destacadas, pueden ser más viejas)."""
    vistos, huellas = set(estado["vistos"]), set(estado["huellas"])
    limite = ahora() - timedelta(days=config["dias_maximos_de_antiguedad"])
    nuevas = 0
    for tag in config["hashtags_a_buscar"]:
        try:
            hid = estado["hashtag_ids"].get(tag)
            if not hid:
                res = api.get("ig_hashtag_search", user_id=ig_id, q=tag)
                if not res.get("data"):
                    continue
                hid = estado["hashtag_ids"][tag] = res["data"][0]["id"]
            try:
                res = api.get(f"{hid}/{tipo}", user_id=ig_id, limit=25,
                              fields="id,caption,permalink,timestamp")
            except ErrorGraph:  # hashtags muy grandes: Instagram pide menos datos por vez
                res = api.get(f"{hid}/{tipo}", user_id=ig_id, limit=10,
                              fields="id,caption,permalink,timestamp")
        except ErrorGraph as e:
            print(f"  #{tag}: no se pudo buscar ({e})")
            continue

        for post in res.get("data", []):
            if post["id"] in vistos:
                continue
            fecha = post.get("timestamp", ahora().strftime("%Y-%m-%dT%H:%M:%S+0000"))
            if datetime.strptime(fecha, "%Y-%m-%dT%H:%M:%S%z") < limite:
                continue  # muy vieja: ni la marcamos como vista
            vistos.add(post["id"])
            estado["vistos"].append(post["id"])
            caption = post.get("caption") or ""
            if not oferta_valida(caption, config):
                continue
            h = huella(caption)
            if h in huellas:
                continue
            huellas.add(h)
            estado["huellas"].append(h)
            estado["cola"].append({"id": post["id"], "caption": caption,
                                   "permalink": post.get("permalink", ""), "timestamp": fecha,
                                   "intentos": 0})
            nuevas += 1
    return nuevas


def ordenar_y_limpiar_cola(estado, config):
    limite = ahora() - timedelta(days=config["dias_maximos_de_antiguedad"])
    cola = [o for o in estado["cola"]
            if datetime.strptime(o["timestamp"], "%Y-%m-%dT%H:%M:%S%z") >= limite
            and oferta_valida(o["caption"], config)]  # por si cambiaron los filtros
    cola.sort(key=lambda o: o["timestamp"], reverse=True)  # lo más nuevo primero
    estado["cola"] = cola


# ---------------------------------------------------------------- publicación

def armar_texto(cuenta, oferta, puesto, zona, contacto, rubro, config):
    lineas = ["🔎 NUEVA BÚSQUEDA LABORAL", "",
              f"💼 Puesto: {puesto[0].upper() + puesto[1:]}",
              f"🏷️ Rubro: {rubro}",
              f"📍 Zona: {zona}"]
    if contacto.get("whatsapp"):
        numero = contacto["whatsapp"]
        lineas.append(f"📲 WhatsApp: {formato_local(numero)} → wa.me/598{numero}")
    if contacto.get("email"):
        lineas.append(f"📩 Email: {contacto['email']}")
    if contacto.get("telefono") and not contacto.get("whatsapp"):
        lineas.append(f"📞 Teléfono: {formato_local(contacto['telefono'])}")
    lineas += ["", AVISO.format(marca=cuenta["logo_texto"]),
               "", "📝 Detalle publicado por la empresa:",
               descripcion_sin_hashtags(oferta["caption"]), ""]
    if oferta.get("permalink"):
        lineas += [f"🔗 Publicación original: {oferta['permalink']}", ""]
    lineas += [f"👉 Seguí a @{cuenta['usuario']} para recibir ofertas todos los días.",
               "🔁 Compartilo con quien esté buscando trabajo.", "",
               f"{config['hashtags_al_publicar']} {cuenta['hashtags_propios']}"]
    return "\n".join(lineas)[:2150]


def texto_para_facebook(cuenta, texto):
    return texto.replace(f"Seguí a @{cuenta['usuario']} para recibir ofertas todos los días.",
                         "Seguí esta página para recibir ofertas todos los días.")


def esperar_contenedor(api, contenedor, intentos=24, espera=5):
    for _ in range(intentos):
        estado = api.get(contenedor, fields="status_code").get("status_code")
        if estado == "FINISHED":
            return
        if estado == "ERROR":
            raise ErrorGraph("Instagram rechazó el archivo")
        time.sleep(espera)
    raise ErrorGraph("Instagram tardó demasiado en procesar el archivo")


def publicar_imagen(api, ig_id, url_imagen, texto=None, historia=False):
    params = {"image_url": url_imagen}
    if historia:
        params["media_type"] = "STORIES"
    else:
        params["caption"] = texto
    for intento in range(4):
        try:
            contenedor = api.post(f"{ig_id}/media", **params)["id"]
            break
        except ErrorGraph:
            if intento == 3:
                raise
            time.sleep(20)  # la imagen recién subida puede tardar unos segundos en estar online
    esperar_contenedor(api, contenedor)
    return api.post(f"{ig_id}/media_publish", creation_id=contenedor)["id"]


def publicar_reel_de_prueba(api, ig_id, ruta_video, texto, graduacion):
    """Sube el video directo a Instagram (sin URL pública) como Reel de prueba:
    se muestra primero a personas que no te siguen."""
    import requests
    respuesta = api.post(f"{ig_id}/media", media_type="REELS", upload_type="resumable",
                         caption=texto, share_to_feed="false",
                         trial_params=json.dumps({"graduation_strategy": graduacion}))
    datos = Path(ruta_video).read_bytes()
    subida = requests.post(respuesta["uri"], data=datos, timeout=300, headers={
        "Authorization": f"OAuth {api.token}", "offset": "0", "file_size": str(len(datos))})
    if not subida.ok or not subida.json().get("success"):
        raise ErrorGraph(f"No se pudo subir el video: {subida.text[:200]}")
    esperar_contenedor(api, respuesta["id"], intentos=40, espera=10)
    return api.post(f"{ig_id}/media_publish", creation_id=respuesta["id"])["id"]


def subir_imagenes(rutas):
    """Publica las imágenes en una rama aparte que se pisa en cada ejecución, para que
    Instagram pueda descargarlas sin que el repositorio crezca con el tiempo."""
    indice = RAIZ / ".git" / "indice-imagenes"
    env = dict(os.environ, GIT_INDEX_FILE=str(indice))

    def g(*args):
        return subprocess.run(["git", *args], cwd=RAIZ, env=env, check=True,
                              capture_output=True, text=True).stdout.strip()

    g("read-tree", "--empty")
    g("update-index", "--add", *[r.relative_to(RAIZ).as_posix() for r in rutas])
    commit = g("commit-tree", g("write-tree"), "-m", "Imágenes para Instagram")
    g("push", "--force", "origin", f"{commit}:refs/heads/{RAMA_IMAGENES}")
    indice.unlink(missing_ok=True)
    return commit


def preparar(cuenta, oferta, config):
    """Una oferta → tarjeta (publicación y Facebook), historia con su rubro y video del Reel de prueba."""
    puesto = extraer_puesto(oferta["caption"])
    zona = extraer_ubicacion(oferta["caption"])
    contacto = extraer_contacto(oferta["caption"])
    rubro = extraer_rubro(puesto, oferta["caption"])
    base = CARPETA_SALIDA / cuenta["clave"] / f"{ahora():%Y%m%d_%H%M}_{oferta['id']}"
    foto = elegir_fondo(puesto, rubro, oferta["caption"]) if config.get("fotos_de_fondo", True) else None
    archivos = {"tarjeta": generar_tarjeta(cuenta, puesto, zona, contacto, base.with_suffix(".jpg"), rubro, foto)}
    if config.get("historias"):
        archivos["historia"] = generar_vertical(cuenta, archivos["tarjeta"],
                                                f"Más info en @{cuenta['usuario']}",
                                                base.with_name(base.name + "_historia.jpg"), rubro)
    if config.get("reels_de_prueba", {}).get("activado"):
        vertical = generar_vertical(cuenta, archivos["tarjeta"], "Toda la info en la descripción",
                                    base.with_name(base.name + "_vertical.jpg"))
        archivos["video"] = generar_video(vertical, base.with_suffix(".mp4"))
    texto = armar_texto(cuenta, oferta, puesto, zona, contacto, rubro, config)
    return {"cuenta": cuenta, "oferta": oferta, "rubro": rubro, "archivos": archivos, "texto": texto}


def paginas_de_facebook(api):
    """IG id → (id de la página de Facebook vinculada, token de esa página)."""
    try:
        datos = api.get("me/accounts", fields="id,access_token,instagram_business_account", limit=100)
    except ErrorGraph as e:
        print(f"  Facebook: no se pudieron leer las páginas ({e})")
        return {}
    return {p["instagram_business_account"]["id"]: (p["id"], p["access_token"])
            for p in datos.get("data", []) if p.get("instagram_business_account")}


def publicar_en_facebook(api, pagina, url_imagen, texto):
    pagina_id, token_pagina = pagina
    import requests
    r = requests.post(f"{api.base}/{pagina_id}/photos", timeout=60, data={
        "url": url_imagen, "message": texto, "access_token": token_pagina})
    return api._respuesta(r)["id"]


# ---------------------------------------------------------------- modos

def modo_prueba(config):
    ejemplos = cargar_json(RAIZ / "ejemplos.json", [])
    salida = RAIZ / "vista_previa"
    for i, oferta in enumerate(ejemplos):
        cuenta = config["cuentas"][i % len(config["cuentas"])]
        aceptada = oferta_valida(oferta["caption"], config)
        print(f"\n=== Ejemplo {i + 1} → @{cuenta['usuario']} | {'ACEPTADA' if aceptada else 'DESCARTADA'}")
        if not aceptada:
            continue
        puesto, zona = extraer_puesto(oferta["caption"]), extraer_ubicacion(oferta["caption"])
        contacto = extraer_contacto(oferta["caption"])
        rubro = extraer_rubro(puesto, oferta["caption"])
        ruta = generar_tarjeta(cuenta, puesto, zona, contacto, salida / f"ejemplo_{i + 1}_{cuenta['clave']}.jpg", rubro,
                              elegir_fondo(puesto, rubro, oferta["caption"]))
        print(armar_texto(cuenta, oferta, puesto, zona, contacto, rubro, config))
        if i == 0:
            generar_vertical(cuenta, ruta, f"Más info en @{cuenta['usuario']}",
                             salida / "ejemplo_historia.jpg", rubro)
            generar_video(generar_vertical(cuenta, ruta, "Toda la info en la descripción",
                                           salida / "ejemplo_reel.jpg"), salida / "ejemplo_reel.mp4")
    print(f"\nTarjetas guardadas en {salida}")


def modo_diagnostico(api, config):
    for cuenta in config["cuentas"]:
        ig_id = os.environ.get(cuenta["variable_id"])
        if not ig_id:
            continue
        print(f"\n=== @{cuenta['usuario']} (últimas publicaciones)")
        datos = api.get(f"{ig_id}/media", limit=14,
                        fields="id,media_type,media_product_type,timestamp,permalink,caption,is_shared_to_feed")
        for m in datos.get("data", []):
            puesto = next((l for l in (m.get("caption") or "").splitlines() if "Puesto" in l), "")
            print(f"{m['timestamp'][:16]} {m.get('media_product_type')}/{m.get('media_type')} "
                  f"feed={m.get('is_shared_to_feed')} {m.get('permalink')} {puesto[:50]}")


def modo_configurar(api):
    paginas = api.get("me/accounts", fields="name,instagram_business_account{id,username}")
    for p in paginas.get("data", []):
        ig = p.get("instagram_business_account")
        if ig:
            print(f"Página '{p['name']}' → @{ig['username']}  ID: {ig['id']}")
        else:
            print(f"Página '{p['name']}' → sin cuenta de Instagram profesional vinculada")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prueba", action="store_true")
    parser.add_argument("--sin-publicar", action="store_true")
    parser.add_argument("--configurar", action="store_true")
    parser.add_argument("--diagnostico", action="store_true")
    args = parser.parse_args()

    config = cargar_json(RAIZ / "config.json", None)
    if args.prueba:
        return modo_prueba(config)

    token = os.environ.get("IG_TOKEN")
    if not token:
        print("Todavía no está cargado el secreto IG_TOKEN: el bot queda en espera (ver GUIA.md, paso 3).")
        return
    api = Graph(token, config["graph_version"])
    if args.configurar:
        return modo_configurar(api)
    if args.diagnostico:
        return modo_diagnostico(api, config)

    cuentas = [c for c in config["cuentas"] if os.environ.get(c["variable_id"])]
    if not cuentas:
        print("Faltan los secretos IG_ID_TCM / IG_ID_BTU: ejecutá 'Ver IDs de mis cuentas' (ver GUIA.md, paso 4).")
        return
    estado = cargar_json(ARCHIVO_ESTADO, estado_inicial())

    print("Buscando ofertas nuevas…")
    ig_busqueda = os.environ[cuentas[0]["variable_id"]]
    nuevas = buscar_ofertas(api, ig_busqueda, config, estado)
    ordenar_y_limpiar_cola(estado, config)
    # Si quedan pocas, se completan con publicaciones destacadas de los últimos días
    if len(estado["cola"]) < config.get("minimo_en_espera", 6):
        extra = buscar_ofertas(api, ig_busqueda, config, estado, tipo="top_media")
        ordenar_y_limpiar_cola(estado, config)
        print(f"  Quedaban pocas: se sumaron {extra} de las destacadas (hasta "
              f"{config['dias_maximos_de_antiguedad']} días).")
    print(f"  {nuevas} ofertas nuevas, {len(estado['cola'])} en espera.")

    # Cada hora, cada cuenta toma UNA oferta y la publica en todos los formatos:
    # publicación + historia (con su rubro) + Reel de prueba + página de Facebook.
    if ahora().hour % 2:  # se alterna qué cuenta elige primero
        cuentas.reverse()
    trabajos = []
    for cuenta in cuentas:
        if not estado["cola"]:
            print(f"  @{cuenta['usuario']}: no hay ofertas nuevas, se saltea esta hora.")
            continue
        trabajos.append(preparar(cuenta, estado["cola"].pop(0), config))

    en_github = os.environ.get("GITHUB_ACTIONS") == "true"
    solo_generar = args.sin_publicar or not en_github  # fuera de GitHub no hay URL pública
    imagenes = [t["archivos"][k] for t in trabajos for k in ("tarjeta", "historia") if k in t["archivos"]]
    sha = subir_imagenes(imagenes) if imagenes and en_github else None
    url = lambda ruta: (f"https://raw.githubusercontent.com/{os.environ['GITHUB_REPOSITORY']}/"
                        f"{sha}/{ruta.relative_to(RAIZ).as_posix()}")
    if sha:
        time.sleep(5)
    paginas = paginas_de_facebook(api) if trabajos and config.get("facebook") and not solo_generar else {}

    errores = 0
    for t in trabajos:
        cuenta, oferta, archivos = t["cuenta"], t["oferta"], t["archivos"]
        quien = f"@{cuenta['usuario']}"
        if solo_generar:
            print(f"  {quien}: generado sin publicar ({t['rubro']}) → " + ", ".join(
                url(r) if sha and r.suffix == ".jpg" else r.name for r in archivos.values()))
            print(t["texto"])
            estado["cola"].insert(0, oferta)  # queda en espera para la próxima publicación real
            continue
        ig_id = os.environ[cuenta["variable_id"]]
        try:
            media_id = publicar_imagen(api, ig_id, url(archivos["tarjeta"]), t["texto"])
        except ErrorGraph as e:
            errores += 1
            print(f"  {quien}: ERROR al publicar → {e}")
            oferta["intentos"] += 1
            if oferta["intentos"] < 2:
                estado["cola"].insert(0, oferta)
            continue
        registro = {"cuenta": cuenta["usuario"], "oferta": oferta["id"], "rubro": t["rubro"],
                    "media": media_id, "fecha": ahora().isoformat()}
        estado["publicados"].append(registro)
        print(f"  {quien}: publicado ✔ [{t['rubro']}] ({oferta['permalink']})")

        # Lo demás es la MISMA oferta en otros formatos; si alguno falla, no frena al resto
        extras = []
        if "historia" in archivos:
            extras.append(("historia", lambda: publicar_imagen(api, ig_id, url(archivos["historia"]),
                                                               historia=True)))
        if "video" in archivos:
            extras.append(("reel de prueba", lambda: publicar_reel_de_prueba(
                api, ig_id, archivos["video"], t["texto"],
                config["reels_de_prueba"].get("graduacion", "MANUAL"))))
        if config.get("facebook"):
            if ig_id in paginas:
                extras.append(("Facebook", lambda: publicar_en_facebook(
                    api, paginas[ig_id], url(archivos["tarjeta"]), texto_para_facebook(cuenta, t["texto"]))))
            else:
                print(f"  {quien}: Facebook → no encontré la página vinculada (¿falta el permiso pages_manage_posts?)")
        for nombre, publicar in extras:
            try:
                registro[nombre] = publicar()
                print(f"  {quien}: {nombre} ✔")
            except ErrorGraph as e:
                print(f"  {quien}: {nombre} → no se pudo ({e})")

    for clave in ("vistos", "huellas", "publicados"):
        estado[clave] = estado[clave][-MAX_HISTORIAL:]
    if not solo_generar:
        estado["ultima_ejecucion"] = ahora().isoformat()  # el workflow lo usa para correr 1 vez por hora
    ARCHIVO_ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")

    if en_github:
        git("add", "estado.json")
        if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=RAIZ).returncode:
            git("commit", "-m", "Actualizar estado")
            for intento in range(4):  # si alguien subió algo mientras tanto, se actualiza y reintenta
                if subprocess.run(["git", "push"], cwd=RAIZ).returncode == 0:
                    break
                subprocess.run(["git", "pull", "--rebase", "-X", "theirs"], cwd=RAIZ)
                time.sleep(3)
            else:
                sys.exit("No se pudo guardar el estado en GitHub.")

    if trabajos and errores == len(trabajos) and not solo_generar:
        sys.exit("No se pudo publicar en ninguna cuenta.")


if __name__ == "__main__":
    main()
