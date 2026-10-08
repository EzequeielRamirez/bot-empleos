"""Genera la tarjeta (1080x1350) con el estilo de la cuenta."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ANCHO, ALTO = 1080, 1350
MARGEN = 70
FUENTES = Path(__file__).parent / "assets" / "fonts"
LOGOS = Path(__file__).parent / "assets"


def fuente(nombre, tam):
    return ImageFont.truetype(str(FUENTES / nombre), tam)


def ancho_texto(draw, texto, f):
    x0, _, x1, _ = draw.textbbox((0, 0), texto, font=f)
    return x1 - x0


def partir_lineas(draw, texto, f, ancho_max):
    lineas, actual = [], ""
    for palabra in texto.split():
        prueba = f"{actual} {palabra}".strip()
        if ancho_texto(draw, prueba, f) <= ancho_max:
            actual = prueba
        else:
            if actual:
                lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas


def ajustar_titulo(draw, texto, ancho_max, alto_max, tam_max=190, tam_min=70):
    """Busca el tamaño más grande que entra en el recuadro."""
    for tam in range(tam_max, tam_min - 1, -6):
        f = fuente("Anton-Regular.ttf", tam)
        lineas = partir_lineas(draw, texto, f, ancho_max)
        alto = len(lineas) * int(tam * 1.12)
        if alto <= alto_max and all(ancho_texto(draw, l, f) <= ancho_max for l in lineas):
            return f, lineas, int(tam * 1.12)
    f = fuente("Anton-Regular.ttf", tam_min)
    return f, partir_lineas(draw, texto, f, ancho_max)[:4], int(tam_min * 1.12)


def pastilla(draw, x, y, texto, f, fondo, color, pad_x=28, pad_y=14):
    w = ancho_texto(draw, texto, f)
    _, t0, _, t1 = draw.textbbox((0, 0), texto, font=f)
    h = t1 - t0
    draw.rounded_rectangle((x, y, x + w + 2 * pad_x, y + h + 2 * pad_y), radius=(h + 2 * pad_y) // 2, fill=fondo)
    draw.text((x + pad_x, y + pad_y - t0), texto, font=f, fill=color)
    return x + w + 2 * pad_x, y + h + 2 * pad_y


def dibujar_logo(img, draw, cuenta, x, y, d):
    archivo = LOGOS / f"logo_{cuenta['clave']}.png"
    if archivo.exists():
        logo = Image.open(archivo).convert("RGBA").resize((d, d))
        mascara = Image.new("L", (d, d), 0)
        ImageDraw.Draw(mascara).ellipse((0, 0, d, d), fill=255)
        img.paste(logo, (x, y), mascara)
        return
    negro = cuenta["color_texto"]
    draw.ellipse((x, y, x + d, y + d), fill=cuenta["color_fondo"], outline=negro, width=9)
    f = fuente("Anton-Regular.ttf", int(d * 0.36))
    w = ancho_texto(draw, cuenta["logo_texto"], f)
    _, t0, _, t1 = draw.textbbox((0, 0), cuenta["logo_texto"], font=f)
    draw.text((x + (d - w) / 2, y + (d - (t1 - t0)) / 2 - t0), cuenta["logo_texto"], font=f, fill=negro)


def icono_ubicacion(draw, x, y, tam, color):
    r = tam * 0.32
    cx, cy = x + tam / 2, y + r + 2
    draw.polygon([(cx - r * 0.85, cy + r * 0.45), (cx + r * 0.85, cy + r * 0.45), (cx, y + tam)], fill=color)
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)
    draw.ellipse((cx - r * 0.4, cy - r * 0.4, cx + r * 0.4, cy + r * 0.4), fill="#111111" if color != "#111111" else "#FFFFFF")


def generar_tarjeta(cuenta, puesto, zona, email, destino):
    fondo, negro, blanco = cuenta["color_fondo"], cuenta["color_texto"], "#FFFFFF"
    img = Image.new("RGB", (ANCHO, ALTO), fondo)
    draw = ImageDraw.Draw(img)

    # Encabezado: logo + usuario
    d = 150
    dibujar_logo(img, draw, cuenta, MARGEN, 60, d)
    draw.text((MARGEN + d + 30, 82), f"@{cuenta['usuario']}", font=fuente("Lato-Black.ttf", 44), fill=negro)
    draw.text((MARGEN + d + 30, 140), cuenta["lema"], font=fuente("Lato-Regular.ttf", 32), fill=negro)

    # Etiqueta
    _, y = pastilla(draw, MARGEN, 270, "OFERTA DE TRABAJO", fuente("Lato-Black.ttf", 34), negro, blanco)

    # Título
    draw.text((MARGEN, y + 30), "SE BUSCA", font=fuente("Anton-Regular.ttf", 84), fill=negro)
    y_titulo = y + 150
    alto_disponible = 930 - y_titulo
    f, lineas, interlineado = ajustar_titulo(draw, puesto.upper(), ANCHO - 2 * MARGEN, alto_disponible)
    y_titulo += max(0, (alto_disponible - len(lineas) * interlineado) // 2)
    for i, linea in enumerate(lineas):
        draw.text((MARGEN - 4, y_titulo + i * interlineado), linea, font=f, fill=blanco,
                  stroke_width=5, stroke_fill=negro)

    # Zona
    fz = fuente("Lato-Black.ttf", 38)
    texto_zona = f"ZONA: {zona.upper()}"
    w = ancho_texto(draw, texto_zona, fz)
    draw.rounded_rectangle((MARGEN, 950, MARGEN + w + 110, 1030), radius=40, fill=negro)
    icono_ubicacion(draw, MARGEN + 26, 966, 48, fondo)
    draw.text((MARGEN + 86, 966), texto_zona, font=fz, fill=blanco)

    # Cómo postularse
    draw.rounded_rectangle((MARGEN, 1060, ANCHO - MARGEN, 1200), radius=28, fill=blanco)
    draw.text((MARGEN + 36, 1080), "¿CÓMO POSTULARSE?", font=fuente("Lato-Black.ttf", 36), fill=negro)
    detalle = f"Enviá tu CV a: {email}" if email else "Toda la información en la descripción"
    fd = fuente("Lato-Bold.ttf", 34)
    while ancho_texto(draw, detalle, fd) > ANCHO - 2 * MARGEN - 140 and fd.size > 22:
        fd = fuente("Lato-Bold.ttf", fd.size - 2)
    draw.text((MARGEN + 36, 1135), detalle, font=fd, fill=negro)
    cx, cy = ANCHO - MARGEN - 60, 1130
    draw.polygon([(cx - 26, cy - 12), (cx + 26, cy - 12), (cx, cy + 22)], fill=fondo)

    # Pie
    draw.rectangle((0, 1240, ANCHO, ALTO), fill=negro)
    fp = fuente("Lato-Bold.ttf", 30)
    pie = f"Seguí a @{cuenta['usuario']} para más ofertas"
    draw.text(((ANCHO - ancho_texto(draw, pie, fp)) / 2, 1260), pie, font=fp, fill=blanco)
    fs = fuente("Lato-Regular.ttf", 22)
    fuente_txt = "Fuente: publicación original de la empresa (datos en la descripción)"
    draw.text(((ANCHO - ancho_texto(draw, fuente_txt, fs)) / 2, 1305), fuente_txt, font=fs, fill="#BBBBBB")

    Path(destino).parent.mkdir(parents=True, exist_ok=True)
    img.save(destino, "JPEG", quality=92)
    return destino


def generar_vertical(cuenta, ruta_tarjeta, texto_inferior, destino):
    """Versión 9:16 (1080x1920) para historias y reels: la tarjeta centrada con encabezado y pie."""
    fondo, negro, blanco = cuenta["color_fondo"], cuenta["color_texto"], "#FFFFFF"
    img = Image.new("RGB", (ANCHO, 1920), negro)
    draw = ImageDraw.Draw(img)

    f = fuente("Anton-Regular.ttf", 76)
    titulo = "NUEVA OFERTA DE TRABAJO"
    draw.text(((ANCHO - ancho_texto(draw, titulo, f)) / 2, 150), titulo, font=f, fill=fondo)

    tarjeta = Image.open(ruta_tarjeta).convert("RGB").resize((1000, 1250))
    mascara = Image.new("L", tarjeta.size, 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, *tarjeta.size), radius=36, fill=255)
    img.paste(tarjeta, (40, 300), mascara)

    fp = fuente("Lato-Black.ttf", 44)
    while ancho_texto(draw, texto_inferior, fp) > ANCHO - 2 * MARGEN and fp.size > 28:
        fp = fuente("Lato-Black.ttf", fp.size - 2)
    draw.text(((ANCHO - ancho_texto(draw, texto_inferior, fp)) / 2, 1610), texto_inferior, font=fp, fill=blanco)
    cx, cy = ANCHO / 2, 1700
    draw.polygon([(cx - 30, cy), (cx + 30, cy), (cx, cy + 34)], fill=fondo)

    Path(destino).parent.mkdir(parents=True, exist_ok=True)
    img.save(destino, "JPEG", quality=92)
    return destino
