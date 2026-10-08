"""Genera (una sola vez, gratis) las fotos de fondo de cada oficio con Pollinations.
Uso: python herramientas/generar_fondos.py [nombre ...]   (sin nombres: genera las que falten)"""
import sys
import time
import urllib.parse
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fondos import CARPETA, OFICIOS  # noqa: E402

ESTILO = ("photorealistic professional stock photo, {}, South American people, the work activity and "
          "tools clearly visible, natural light, candid, modest work clothes, high quality, no text, "
          "no watermark, no logo")


def generar(nombre, descripcion, semilla=23):
    url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(ESTILO.format(descripcion))
           + f"?width=1080&height=1350&seed={semilla}&model=flux&nologo=true")
    for intento in range(4):
        r = requests.get(url, timeout=180)
        if r.ok and r.headers.get("content-type", "").startswith("image"):
            (CARPETA / f"{nombre}.jpg").write_bytes(r.content)
            return True
        time.sleep(15 * (intento + 1))
    return False


if __name__ == "__main__":
    CARPETA.mkdir(parents=True, exist_ok=True)
    nombres = sys.argv[1:] or [n for n in OFICIOS if not (CARPETA / f"{n}.jpg").exists()]
    for n in nombres:
        ok = generar(n, OFICIOS[n][1])
        print(("✔ " if ok else "✘ ") + n, flush=True)
        time.sleep(6)
