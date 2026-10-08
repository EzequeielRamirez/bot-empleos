"""Busca búsquedas laborales recientes en Instagram (por hashtags) y publica
una tarjeta propia en cada cuenta configurada.

Uso:
  python bot.py                 # busca y publica (lo que corre cada hora en GitHub)
  python bot.py --sin-publicar  # busca y genera las tarjetas, pero no publica
  python bot.py --prueba        # sin internet: genera tarjetas de ejemplo en vista_previa/
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

from extraccion import (descripcion_sin_hashtags, es_busqueda_laboral, extraer_email,
                        extraer_puesto, extraer_zona, huella)
from tarjeta import generar_tarjeta

RAIZ = Path(__file__).parent
ARCHIVO_ESTADO = RAIZ / "estado.json"
CARPETA_IMAGENES = RAIZ / "publicadas"
MAX_HISTORIAL = 5000


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

def buscar_ofertas(api, ig_id, config, estado):
    vistos, huellas = set(estado["vistos"]), set(estado["huellas"])
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
                res = api.get(f"{hid}/recent_media", user_id=ig_id, limit=25,
                              fields="id,caption,permalink,timestamp")
            except ErrorGraph:  # hashtags muy grandes: Instagram pide menos datos por vez
                res = api.get(f"{hid}/recent_media", user_id=ig_id, limit=10,
                              fields="id,caption,permalink,timestamp")
        except ErrorGraph as e:
            print(f"  #{tag}: no se pudo buscar ({e})")
            continue

        for post in res.get("data", []):
            if post["id"] in vistos:
                continue
            vistos.add(post["id"])
            estado["vistos"].append(post["id"])
            caption = post.get("caption") or ""
            if not es_busqueda_laboral(caption, config):
                continue
            h = huella(caption)
            if h in huellas:
                continue
            huellas.add(h)
            estado["huellas"].append(h)
            estado["cola"].append({
                "id": post["id"], "caption": caption, "permalink": post.get("permalink", ""),
                "timestamp": post.get("timestamp", ahora().strftime("%Y-%m-%dT%H:%M:%S+0000")),
                "intentos": 0,
            })
            nuevas += 1
    return nuevas


def ordenar_y_limpiar_cola(estado, config):
    limite = ahora() - timedelta(days=config["dias_maximos_de_antiguedad"])
    cola = [o for o in estado["cola"]
            if datetime.strptime(o["timestamp"], "%Y-%m-%dT%H:%M:%S%z") >= limite
            and es_busqueda_laboral(o["caption"], config)]  # por si cambiaron los filtros
    cola.sort(key=lambda o: o["timestamp"], reverse=True)  # lo más nuevo primero
    estado["cola"] = cola


# ---------------------------------------------------------------- publicación

def armar_texto(cuenta, oferta, puesto, zona, email, config):
    lineas = ["🔎 NUEVA BÚSQUEDA LABORAL", "",
              f"💼 Puesto: {puesto[0].upper() + puesto[1:]}",
              f"📍 Zona: {zona}"]
    if email:
        lineas.append(f"📩 Contacto: {email}")
    lineas += ["", "📝 Detalle publicado por la empresa:",
               descripcion_sin_hashtags(oferta["caption"]), ""]
    if oferta.get("permalink"):
        lineas += [f"🔗 Publicación original: {oferta['permalink']}", ""]
    lineas += [f"👉 Seguí a @{cuenta['usuario']} para recibir ofertas todos los días.",
               "🔁 Compartilo con quien esté buscando trabajo.", "",
               f"{config['hashtags_al_publicar']} {cuenta['hashtags_propios']}"]
    return "\n".join(lineas)[:2150]


def publicar_en_instagram(api, ig_id, url_imagen, texto):
    for intento in range(4):
        try:
            contenedor = api.post(f"{ig_id}/media", image_url=url_imagen, caption=texto)["id"]
            break
        except ErrorGraph:
            if intento == 3:
                raise
            time.sleep(20)  # la imagen recién subida puede tardar unos segundos en estar online
    for _ in range(24):
        estado = api.get(contenedor, fields="status_code").get("status_code")
        if estado == "FINISHED":
            break
        if estado == "ERROR":
            raise ErrorGraph("Instagram rechazó la imagen")
        time.sleep(5)
    return api.post(f"{ig_id}/media_publish", creation_id=contenedor)["id"]


def preparar(cuenta, oferta, config):
    puesto = extraer_puesto(oferta["caption"])
    zona = extraer_zona(oferta["caption"])
    email = extraer_email(oferta["caption"])
    nombre = f"{ahora():%Y%m%d_%H%M}_{cuenta['clave']}_{oferta['id']}.jpg"
    ruta = CARPETA_IMAGENES / cuenta["clave"] / nombre
    generar_tarjeta(cuenta, puesto, zona, email, ruta)
    texto = armar_texto(cuenta, oferta, puesto, zona, email, config)
    return ruta, texto


def borrar_imagenes_viejas(config):
    corte = (ahora() - timedelta(days=config["dias_que_se_guardan_las_imagenes"])).strftime("%Y%m%d")
    for img in CARPETA_IMAGENES.glob("*/*.jpg"):
        if img.name[:8] < corte:
            img.unlink()


# ---------------------------------------------------------------- modos

def modo_prueba(config):
    ejemplos = cargar_json(RAIZ / "ejemplos.json", [])
    salida = RAIZ / "vista_previa"
    for i, oferta in enumerate(ejemplos):
        cuenta = config["cuentas"][i % len(config["cuentas"])]
        aceptada = es_busqueda_laboral(oferta["caption"], config)
        print(f"\n=== Ejemplo {i + 1} → @{cuenta['usuario']} | {'ACEPTADA' if aceptada else 'DESCARTADA'}")
        if not aceptada:
            continue
        puesto, zona, email = (extraer_puesto(oferta["caption"]), extraer_zona(oferta["caption"]),
                               extraer_email(oferta["caption"]))
        generar_tarjeta(cuenta, puesto, zona, email, salida / f"ejemplo_{i + 1}_{cuenta['clave']}.jpg")
        print(armar_texto(cuenta, oferta, puesto, zona, email, config))
    print(f"\nTarjetas guardadas en {salida}")


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

    cuentas = [c for c in config["cuentas"] if os.environ.get(c["variable_id"])]
    if not cuentas:
        print("Faltan los secretos IG_ID_TCM / IG_ID_BTU: ejecutá 'Ver IDs de mis cuentas' (ver GUIA.md, paso 4).")
        return
    estado = cargar_json(ARCHIVO_ESTADO, estado_inicial())

    print("Buscando ofertas nuevas…")
    nuevas = buscar_ofertas(api, os.environ[cuentas[0]["variable_id"]], config, estado)
    ordenar_y_limpiar_cola(estado, config)
    print(f"  {nuevas} ofertas nuevas, {len(estado['cola'])} en espera.")

    # Cada hora se alterna qué cuenta elige primero, y cada cuenta publica una oferta distinta
    if ahora().hour % 2:
        cuentas.reverse()
    trabajos = []
    for cuenta in cuentas:
        if not estado["cola"]:
            print(f"  @{cuenta['usuario']}: no hay ofertas nuevas, se saltea esta hora.")
            continue
        oferta = estado["cola"].pop(0)
        ruta, texto = preparar(cuenta, oferta, config)
        trabajos.append((cuenta, oferta, ruta, texto))

    en_github = os.environ.get("GITHUB_ACTIONS") == "true"
    solo_generar = args.sin_publicar or not en_github  # fuera de GitHub no hay URL pública
    if trabajos and not solo_generar:
        # Las imágenes se suben al repositorio para que Instagram pueda descargarlas
        git("add", "publicadas")
        git("commit", "-m", "Tarjetas nuevas")
        git("push")
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=RAIZ, capture_output=True,
                             text=True, check=True).stdout.strip()
        time.sleep(5)

    errores = 0
    for cuenta, oferta, ruta, texto in trabajos:
        if solo_generar:
            print(f"  @{cuenta['usuario']}: tarjeta generada en {ruta} (sin publicar)")
            print(texto)
            estado["cola"].insert(0, oferta)  # queda en espera para la próxima publicación real
            continue
        relativa = ruta.relative_to(RAIZ).as_posix()
        url = f"https://raw.githubusercontent.com/{os.environ['GITHUB_REPOSITORY']}/{sha}/{relativa}"
        try:
            media_id = publicar_en_instagram(api, os.environ[cuenta["variable_id"]], url, texto)
            estado["publicados"].append({"cuenta": cuenta["usuario"], "oferta": oferta["id"],
                                         "media": media_id, "fecha": ahora().isoformat()})
            print(f"  @{cuenta['usuario']}: publicado ✔ ({oferta['permalink']})")
        except ErrorGraph as e:
            errores += 1
            print(f"  @{cuenta['usuario']}: ERROR al publicar → {e}")
            oferta["intentos"] += 1
            if oferta["intentos"] < 2:
                estado["cola"].insert(0, oferta)

    for clave in ("vistos", "huellas", "publicados"):
        estado[clave] = estado[clave][-MAX_HISTORIAL:]
    ARCHIVO_ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")
    borrar_imagenes_viejas(config)

    if en_github:
        git("add", "-A", "estado.json", "publicadas")
        if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=RAIZ).returncode:
            git("commit", "-m", "Actualizar estado")
            git("push")

    if trabajos and errores == len(trabajos) and not solo_generar:
        sys.exit("No se pudo publicar en ninguna cuenta.")


if __name__ == "__main__":
    main()
