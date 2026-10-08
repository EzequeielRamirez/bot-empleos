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

from extraccion import (descripcion_sin_hashtags, es_busqueda_laboral, extraer_email,
                        extraer_puesto, extraer_zona, huella)
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
    lineas += ["", AVISO.format(marca=cuenta["logo_texto"]),
               "", "📝 Detalle publicado por la empresa:",
               descripcion_sin_hashtags(oferta["caption"]), ""]
    if oferta.get("permalink"):
        lineas += [f"🔗 Publicación original: {oferta['permalink']}", ""]
    lineas += [f"👉 Seguí a @{cuenta['usuario']} para recibir ofertas todos los días.",
               "🔁 Compartilo con quien esté buscando trabajo.", "",
               f"{config['hashtags_al_publicar']} {cuenta['hashtags_propios']}"]
    return "\n".join(lineas)[:2150]


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


def preparar(cuenta, oferta, config, formato):
    """formato: "feed" (tarjeta + historia) o "reel"."""
    puesto = extraer_puesto(oferta["caption"])
    zona = extraer_zona(oferta["caption"])
    email = extraer_email(oferta["caption"])
    base = CARPETA_SALIDA / cuenta["clave"] / f"{ahora():%Y%m%d_%H%M}_{formato}_{oferta['id']}"
    archivos = {"tarjeta": generar_tarjeta(cuenta, puesto, zona, email, base.with_suffix(".jpg"))}
    if formato == "feed" and config.get("historias"):
        archivos["historia"] = generar_vertical(cuenta, archivos["tarjeta"],
                                                f"Más info en @{cuenta['usuario']}",
                                                base.with_name(base.name + "_historia.jpg"))
    if formato == "reel":
        vertical = generar_vertical(cuenta, archivos["tarjeta"], "Toda la info en la descripción",
                                    base.with_name(base.name + "_vertical.jpg"))
        archivos["video"] = generar_video(vertical, base.with_suffix(".mp4"))
    texto = armar_texto(cuenta, oferta, puesto, zona, email, config)
    return {"cuenta": cuenta, "oferta": oferta, "formato": formato,
            "archivos": archivos, "texto": texto}


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
        ruta = generar_tarjeta(cuenta, puesto, zona, email, salida / f"ejemplo_{i + 1}_{cuenta['clave']}.jpg")
        print(armar_texto(cuenta, oferta, puesto, zona, email, config))
        if i == 0:
            historia = generar_vertical(cuenta, ruta, f"Más info en @{cuenta['usuario']}",
                                        salida / "ejemplo_historia.jpg")
            generar_video(generar_vertical(cuenta, ruta, "Toda la info en la descripción",
                                           salida / "ejemplo_reel.jpg"), salida / "ejemplo_reel.mp4")
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

    # Cada hora se alterna qué cuenta elige primero. Primero se reparten las publicaciones
    # normales (que también van a historias); si sobran ofertas, van como Reels de prueba,
    # que NO se comparten en historias para no repetir el mismo anuncio.
    if ahora().hour % 2:
        cuentas.reverse()
    trabajos = []
    for cuenta in cuentas:
        if not estado["cola"]:
            print(f"  @{cuenta['usuario']}: no hay ofertas nuevas, se saltea esta hora.")
            continue
        trabajos.append(preparar(cuenta, estado["cola"].pop(0), config, "feed"))
    reels = config.get("reels_de_prueba", {})
    if reels.get("activado"):
        for _ in range(reels.get("por_hora_por_cuenta", 1)):
            for cuenta in cuentas:
                if estado["cola"]:
                    trabajos.append(preparar(cuenta, estado["cola"].pop(0), config, "reel"))

    en_github = os.environ.get("GITHUB_ACTIONS") == "true"
    solo_generar = args.sin_publicar or not en_github  # fuera de GitHub no hay URL pública
    imagenes = [t["archivos"][k] for t in trabajos for k in ("tarjeta", "historia") if k in t["archivos"]]
    sha = subir_imagenes(imagenes) if imagenes and en_github else None
    url = lambda ruta: (f"https://raw.githubusercontent.com/{os.environ['GITHUB_REPOSITORY']}/"
                        f"{sha}/{ruta.relative_to(RAIZ).as_posix()}")
    if sha:
        time.sleep(5)

    errores = 0
    for t in trabajos:
        cuenta, oferta, archivos = t["cuenta"], t["oferta"], t["archivos"]
        quien = f"@{cuenta['usuario']} ({'publicación' if t['formato'] == 'feed' else 'reel de prueba'})"
        if solo_generar:
            print(f"  {quien}: generado sin publicar → " + ", ".join(
                url(r) if sha and r.suffix == ".jpg" else r.name for r in archivos.values()))
            print(t["texto"])
            estado["cola"].insert(0, oferta)  # queda en espera para la próxima publicación real
            continue
        ig_id = os.environ[cuenta["variable_id"]]
        try:
            if t["formato"] == "feed":
                media_id = publicar_imagen(api, ig_id, url(archivos["tarjeta"]), t["texto"])
            else:
                media_id = publicar_reel_de_prueba(api, ig_id, archivos["video"], t["texto"],
                                                   reels.get("graduacion", "MANUAL"))
            estado["publicados"].append({"cuenta": cuenta["usuario"], "formato": t["formato"],
                                         "oferta": oferta["id"], "media": media_id,
                                         "fecha": ahora().isoformat()})
            print(f"  {quien}: publicado ✔ ({oferta['permalink']})")
        except ErrorGraph as e:
            errores += 1
            print(f"  {quien}: ERROR al publicar → {e}")
            oferta["intentos"] += 1
            if oferta["intentos"] < 2:
                estado["cola"].insert(0, oferta)
            continue
        if "historia" in archivos:
            try:
                publicar_imagen(api, ig_id, url(archivos["historia"]), historia=True)
                print(f"  @{cuenta['usuario']}: compartido en historias ✔")
            except ErrorGraph as e:
                print(f"  @{cuenta['usuario']}: no se pudo subir la historia → {e}")

    for clave in ("vistos", "huellas", "publicados"):
        estado[clave] = estado[clave][-MAX_HISTORIAL:]
    ARCHIVO_ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")

    if en_github:
        git("add", "estado.json")
        if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=RAIZ).returncode:
            git("commit", "-m", "Actualizar estado")
            git("push")

    if trabajos and errores == len(trabajos) and not solo_generar:
        sys.exit("No se pudo publicar nada.")


if __name__ == "__main__":
    main()
