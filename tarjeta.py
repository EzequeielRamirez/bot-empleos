"""Genera la tarjeta (1080x1350) con el estilo de la cuenta."""
from pathlib import Path

from extraccion import formato_local

from PIL import Image, ImageDraw, ImageFilter, ImageFont

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


# ---------------------------------------------------------------- piezas de diseño
# Los elementos redondos se dibujan 4 veces más grandes y se achican: bordes suaves.
SS = 4
DEGRADE_CENTRO, DEGRADE_BORDE = (252, 193, 8), (247, 132, 2)   # el mismo naranja de los logos
COLORES_IG = [(254, 218, 117), (250, 126, 30), (214, 41, 118), (150, 47, 191), (79, 91, 213)]
AZUL_VERIFICADO = (0, 149, 246)
VERDE_WHATSAPP = (37, 211, 102)


def fondo_degradado(ancho, alto):
    mascara = Image.radial_gradient("L").resize((ancho, alto), Image.LANCZOS)
    return Image.composite(Image.new("RGB", (ancho, alto), DEGRADE_BORDE),
                           Image.new("RGB", (ancho, alto), DEGRADE_CENTRO), mascara)


def degradado_lineal(tam, colores):
    """Degradé diagonal (abajo-izquierda → arriba-derecha), como el aro de las historias."""
    franja = Image.new("RGB", (len(colores), 1))
    franja.putdata(colores)
    franja = franja.resize((tam * 2, 1), Image.BILINEAR).resize((tam * 2, tam * 2))
    return franja.rotate(45, resample=Image.BICUBIC).crop((tam // 2, tam // 2, tam // 2 + tam, tam // 2 + tam))


def avatar(cuenta, d):
    """Logo circular con el aro de colores de Instagram y borde blanco."""
    D = d * SS
    capa = Image.new("RGBA", (D, D), (0, 0, 0, 0))
    aro = degradado_lineal(D, COLORES_IG).convert("RGBA")
    m = Image.new("L", (D, D), 0)
    ImageDraw.Draw(m).ellipse((0, 0, D - 1, D - 1), fill=255)
    capa.paste(aro, (0, 0), m)
    g = int(D * 0.045)
    ImageDraw.Draw(capa).ellipse((g, g, D - g, D - g), fill=(255, 255, 255, 255))
    g2 = int(D * 0.085)
    interior = D - 2 * g2
    archivo = LOGOS / f"logo_{cuenta['clave']}.png"
    if archivo.exists():
        logo = Image.open(archivo).convert("RGBA")
        lado = logo.width
        # Cuánto se amplía el logo dentro del círculo (BTU es más ancho y necesita aire)
        recorte = int(lado * cuenta.get("logo_recorte", 0.1))
        if recorte < 0:  # achicar: se agrega margen con el mismo degradé de fondo
            grande = fondo_degradado(lado - 2 * recorte, lado - 2 * recorte).convert("RGBA")
            grande.paste(logo, (-recorte, -recorte))
            logo = grande.resize((interior, interior), Image.LANCZOS)
        else:
            logo = logo.crop((recorte, recorte, lado - recorte, lado - recorte)).resize(
                (interior, interior), Image.LANCZOS)
    else:
        logo = fondo_degradado(interior, interior).convert("RGBA")
        dl = ImageDraw.Draw(logo)
        f = fuente("Anton-Regular.ttf", int(interior * 0.36))
        w = ancho_texto(dl, cuenta["logo_texto"], f)
        dl.text(((interior - w) / 2, interior * 0.28), cuenta["logo_texto"], font=f, fill="#111111")
    mi = Image.new("L", (interior, interior), 0)
    ImageDraw.Draw(mi).ellipse((0, 0, interior - 1, interior - 1), fill=255)
    capa.paste(logo, (g2, g2), mi)
    return capa.resize((d, d), Image.LANCZOS)


def insignia_verificado(d):
    """Insignia azul de cuenta verificada (círculo con ondas y tilde blanco)."""
    D = d * SS
    capa = Image.new("RGBA", (D, D), (0, 0, 0, 0))
    dr = ImageDraw.Draw(capa)
    c, r = D / 2, D * 0.40
    import math
    for i in range(16):
        ang = 2 * math.pi * i / 16
        x, y = c + r * 0.86 * math.cos(ang), c + r * 0.86 * math.sin(ang)
        dr.ellipse((x - r * 0.3, y - r * 0.3, x + r * 0.3, y + r * 0.3), fill=AZUL_VERIFICADO)
    dr.ellipse((c - r * 0.92, c - r * 0.92, c + r * 0.92, c + r * 0.92), fill=AZUL_VERIFICADO)
    dr.line([(c - r * 0.42, c + r * 0.02), (c - r * 0.1, c + r * 0.34), (c + r * 0.46, c - r * 0.3)],
            fill="white", width=int(D * 0.09), joint="curve")
    return capa.resize((d, d), Image.LANCZOS)


def icono_contacto(tipo, d):
    """Círculo con ícono: WhatsApp (globo de chat), email (sobre) o info."""
    D = d * SS
    capa = Image.new("RGBA", (D, D), (0, 0, 0, 0))
    dr = ImageDraw.Draw(capa)
    color = {"whatsapp": VERDE_WHATSAPP, "email": (17, 17, 17), "info": (17, 17, 17)}[tipo]
    dr.ellipse((0, 0, D - 1, D - 1), fill=color)
    c, w = D / 2, int(D * 0.06)
    if tipo == "whatsapp":
        # globo de chat con colita abajo a la izquierda + auricular adentro
        import math
        r = D * 0.28
        dr.ellipse((c - r, c - r, c + r, c + r), outline="white", width=w)
        dr.polygon([(c - r * 0.72, c + r * 0.62), (c - r * 1.08, c + r * 1.08), (c - r * 0.3, c + r * 0.93)],
                   fill="white")
        dr.ellipse((c - r + w, c - r + w, c + r - w, c + r - w), fill=color)  # tapa la base de la colita
        a = r * 0.5
        grosor = int(D * 0.07)
        dr.arc((c - a, c - a, c + a, c + a), start=35, end=235, fill="white", width=grosor)
        for ang in (35, 235):
            x, y = c + (a - grosor / 2) * math.cos(math.radians(ang)), c + (a - grosor / 2) * math.sin(math.radians(ang))
            e = D * 0.052
            dr.ellipse((x - e, y - e, x + e, y + e), fill="white")
    elif tipo == "email":
        x0, y0, x1, y1 = c - D * 0.24, c - D * 0.16, c + D * 0.24, c + D * 0.16
        dr.rectangle((x0, y0, x1, y1), outline="white", width=w)
        dr.line([(x0, y0), (c, c + D * 0.03), (x1, y0)], fill="white", width=w, joint="curve")
    else:
        f = fuente("Anton-Regular.ttf", int(D * 0.55))
        dr.text((c, c), "i", font=f, fill="white", anchor="mm")
    return capa.resize((d, d), Image.LANCZOS)


def sombra(img, caja, radio, desplazamiento=10, opacidad=70):
    capa = Image.new("RGBA", img.size, (0, 0, 0, 0))
    x0, y0, x1, y1 = caja
    ImageDraw.Draw(capa).rounded_rectangle((x0, y0 + desplazamiento, x1, y1 + desplazamiento),
                                           radius=radio, fill=(0, 0, 0, opacidad))
    capa = capa.filter(ImageFilter.GaussianBlur(14))
    img.alpha_composite(capa)


# ---------------------------------------------------------------- tarjeta

def generar_tarjeta(cuenta, puesto, zona, contacto, destino, rubro=None):
    negro, blanco = "#111111", "#FFFFFF"
    img = fondo_degradado(ANCHO, ALTO).convert("RGBA")
    draw = ImageDraw.Draw(img)

    # Encabezado estilo Instagram: logo con aro, usuario + verificado, lema
    d = 132
    img.alpha_composite(avatar(cuenta, d), (MARGEN - 6, 58))
    fu = fuente("Lato-Black.ttf", 46)
    x_txt = MARGEN + d + 22
    draw.text((x_txt, 76), cuenta["usuario"], font=fu, fill=negro)
    img.alpha_composite(insignia_verificado(44), (int(x_txt + ancho_texto(draw, cuenta["usuario"], fu) + 12), 80))
    draw.text((x_txt, 136), cuenta["lema"], font=fuente("Lato-Regular.ttf", 31), fill="#3B2A00")
    draw.line((MARGEN, 222, ANCHO - MARGEN, 222), fill=(17, 17, 17, 60), width=2)

    # Etiqueta + título
    _, y = pastilla(draw, MARGEN, 252, "OFERTA DE TRABAJO", fuente("Lato-Black.ttf", 30), negro, blanco, 26, 12)
    draw.text((MARGEN, y + 22), "SE BUSCA", font=fuente("Anton-Regular.ttf", 84), fill=negro)
    y_titulo = y + 140
    alto_disponible = 905 - y_titulo
    f, lineas, interlineado = ajustar_titulo(draw, puesto.upper(), ANCHO - 2 * MARGEN, alto_disponible)
    y_titulo += max(0, (alto_disponible - len(lineas) * interlineado) // 2)
    for i, linea in enumerate(lineas):  # sombra suave + texto con contorno
        draw.text((MARGEN - 4 + 6, y_titulo + i * interlineado + 8), linea, font=f, fill=(0, 0, 0, 70))
    for i, linea in enumerate(lineas):
        draw.text((MARGEN - 4, y_titulo + i * interlineado), linea, font=f, fill=blanco,
                  stroke_width=5, stroke_fill=negro)

    # Zona y rubro
    fz = fuente("Lato-Black.ttf", 32)
    texto_zona = zona.upper()
    w = ancho_texto(draw, texto_zona, fz)
    draw.rounded_rectangle((MARGEN, 930, MARGEN + w + 96, 998), radius=34, fill=negro)
    icono_ubicacion(draw, MARGEN + 24, 942, 44, DEGRADE_CENTRO)
    draw.text((MARGEN + 76, 945), texto_zona, font=fz, fill=blanco)
    if rubro:
        texto_rubro = rubro.upper()
        fr = fuente("Lato-Black.ttf", 26)
        while ancho_texto(draw, texto_rubro, fr) > ANCHO - 2 * MARGEN - w - 160 and fr.size > 18:
            fr = fuente("Lato-Black.ttf", fr.size - 1)
        x_r = MARGEN + w + 116
        wr = ancho_texto(draw, texto_rubro, fr)
        draw.rounded_rectangle((x_r, 930, x_r + wr + 48, 998), radius=34, fill=(255, 255, 255, 235))
        draw.text((x_r + 24, 964), texto_rubro, font=fr, fill=negro, anchor="lm")

    # Cómo postularse: tarjeta blanca con sombra e ícono
    caja = (MARGEN, 1028, ANCHO - MARGEN, 1192)
    sombra(img, caja, 30)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(caja, radius=30, fill=blanco)
    if contacto.get("whatsapp"):
        tipo, etiqueta, dato = "whatsapp", "POSTULATE POR WHATSAPP", formato_local(contacto["whatsapp"])
    elif contacto.get("email"):
        tipo, etiqueta, dato = "email", "ENVIÁ TU CV A", contacto["email"]
    else:
        tipo, etiqueta, dato = "info", "¿CÓMO POSTULARSE?", "Toda la información en la descripción"
    img.alpha_composite(icono_contacto(tipo, 92), (MARGEN + 30, 1064))
    x_c = MARGEN + 146
    draw.text((x_c, 1066), etiqueta, font=fuente("Lato-Black.ttf", 26), fill="#7A7A7A")
    fd = fuente("Lato-Black.ttf", 50 if tipo == "whatsapp" else 36)
    while ancho_texto(draw, dato, fd) > caja[2] - x_c - 30 and fd.size > 22:
        fd = fuente("Lato-Black.ttf", fd.size - 2)
    draw.text((x_c, 1146), dato, font=fd, fill=negro, anchor="lm")

    # Pie
    draw.rectangle((0, 1232, ANCHO, ALTO), fill=negro)
    fp = fuente("Lato-Bold.ttf", 30)
    pie = f"Seguí a @{cuenta['usuario']} para más ofertas"
    x_p = (ANCHO - ancho_texto(draw, pie, fp) - 40) / 2
    draw.text((x_p, 1252), pie, font=fp, fill=blanco)
    img.alpha_composite(insignia_verificado(30), (int(x_p + ancho_texto(draw, pie, fp) + 10), 1254))
    fs = fuente("Lato-Regular.ttf", 22)
    fuente_txt = "Difusión de ofertas · Fuente: publicación original de la empresa"
    draw.text(((ANCHO - ancho_texto(draw, fuente_txt, fs)) / 2, 1300), fuente_txt, font=fs, fill="#AAAAAA")

    Path(destino).parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(destino, "JPEG", quality=93)
    return destino


def generar_vertical(cuenta, ruta_tarjeta, texto_inferior, destino, rubro=None):
    """Versión 9:16 (1080x1920) para historias y reels: la tarjeta centrada con encabezado y pie."""
    fondo, negro, blanco = cuenta["color_fondo"], cuenta["color_texto"], "#FFFFFF"
    img = Image.new("RGB", (ANCHO, 1920), negro)
    draw = ImageDraw.Draw(img)

    f = fuente("Anton-Regular.ttf", 76)
    titulo = "NUEVA OFERTA DE TRABAJO"
    draw.text(((ANCHO - ancho_texto(draw, titulo, f)) / 2, 110 if rubro else 150), titulo, font=f, fill=fondo)
    if rubro:
        fr = fuente("Lato-Black.ttf", 34)
        etiqueta = f"RUBRO: {rubro.upper()}"
        w = ancho_texto(draw, etiqueta, fr)
        pastilla(draw, (ANCHO - w) / 2 - 28, 212, etiqueta, fr, blanco, negro)

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
