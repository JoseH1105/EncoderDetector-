"""
Visualización: imágenes anotadas, gráficas de perfil/espectro y tablas HTML.

Paleta tomada del propio objeto: acrílico blanco, fondo negro mate,
azul de la marca, rojo de las manchas.
"""
import math

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from . import config as C  # noqa: E402
from .caracteristicas import paso  # noqa: E402

# colores (hex para HTML/matplotlib, BGR para OpenCV)
TINTA = "#1d2430"
GRIS = "#8a93a3"
AZUL = "#3446d4"
ROJO = "#d23b3b"
VERDE = "#1f8a5b"
AMBAR = "#c98a12"
AMBAR_CLARO = "#f2c200"     # recuadro de ancho incorrecto (amarillo visible sobre blanco y negro)


def _bgr(hexa):
    h = hexa.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (4, 2, 0))


def a_rgb(img):
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def _fig_a_img(fig):
    fig.canvas.draw()
    img = np.asarray(fig.canvas.buffer_rgba())[:, :, :3].copy()
    plt.close(fig)
    return img


def _texto(img, txt, org, escala=0.7, color=(255, 255, 255), grosor=2):
    cv2.putText(img, txt, org, cv2.FONT_HERSHEY_SIMPLEX, escala, (0, 0, 0), grosor + 3, cv2.LINE_AA)
    cv2.putText(img, txt, org, cv2.FONT_HERSHEY_SIMPLEX, escala, color, grosor, cv2.LINE_AA)


# ------------------------------------------------------------------ disco ubicado

LADO_VISTA = 1000          # lado de la vista del resultado (px)
MARGEN_VISTA = 1.35        # recorte alrededor del disco, en semiejes mayores


def _vista_original(adq, geo):
    """Recorte de la foto original alrededor del disco, llevado a LADO_VISTA px.
    Devuelve (imagen BGR, función que pasa puntos de I0 a la vista, escala q)."""
    I0 = adq["I0"]
    H, W = I0.shape[:2]
    m = MARGEN_VISTA * geo["a"]
    x0, y0 = int(round(geo["xc"] - m)), int(round(geo["yc"] - m))
    lado = int(round(2 * m))
    lienzo = np.zeros((lado, lado, 3), np.uint8)
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + lado), min(H, y0 + lado)
    lienzo[ya - y0:yb - y0, xa - x0:xb - x0] = I0[ya:yb, xa:xb]
    q = LADO_VISTA / lado
    interp = cv2.INTER_AREA if q < 1 else cv2.INTER_LINEAR
    vista = cv2.resize(lienzo, (LADO_VISTA, LADO_VISTA), interpolation=interp)

    def a_vista(pts):
        pts = np.asarray(pts, np.float64).reshape(-1, 2)
        return (pts - [x0, y0]) * q
    return vista, a_vista, q


def _dibujar_segmentacion(img, cx, cy, a, b, phi):
    """Borde (verde), anillos de la corona (blanco), franja de conteo (azul) y centro."""
    def elipse(f):
        return ((cx, cy), (2 * a * f, 2 * b * f), phi)

    banda = np.zeros(img.shape[:2], np.uint8)
    cv2.ellipse(banda, elipse(C.BANDA_MUESTREO[1]), 255, -1)
    cv2.ellipse(banda, elipse(C.BANDA_MUESTREO[0]), 0, -1)
    img[banda > 0] = (0.8 * img[banda > 0] + 0.2 * np.array(_bgr(AZUL))).astype(np.uint8)
    g = max(1, int(round(a / 150)))
    cv2.ellipse(img, elipse(1.0), _bgr(VERDE), 2 * g, cv2.LINE_AA)
    for f in C.BANDA_CORONA:
        cv2.ellipse(img, elipse(f), (255, 255, 255), g, cv2.LINE_AA)
    t = int(a * 0.08)
    cv2.line(img, (int(cx - t), int(cy)), (int(cx + t), int(cy)), _bgr(VERDE), 2 * g, cv2.LINE_AA)
    cv2.line(img, (int(cx), int(cy - t)), (int(cx), int(cy + t)), _bgr(VERDE), 2 * g, cv2.LINE_AA)


def segmentacion(adq, geo):
    """Foto original recortada con la segmentación: borde, anillos y franja de conteo."""
    if not geo.get("ok"):
        out = adq["I_loc"].copy()
        cnt, _ = cv2.findContours(geo["mascara"], cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(out, cnt, -1, _bgr(ROJO), 2)
        return a_rgb(out)
    img, a_vista, q = _vista_original(adq, geo)
    (cx, cy), = a_vista([geo["xc"], geo["yc"]])
    _dibujar_segmentacion(img, cx, cy, geo["a"] * q, geo["b"] * q, geo["phi"])
    return a_rgb(img)


# ------------------------------------------------------------------ ruido

def antes_despues(I_n, I_f, zoom=0.22):
    """Disco normalizado antes/después y un acercamiento al borde de un hueco."""
    L = C.LADO_N
    lado = 520
    a = cv2.resize(I_n, (lado, lado), interpolation=cv2.INTER_AREA)
    b = cv2.resize(I_f, (lado, lado), interpolation=cv2.INTER_AREA)
    # acercamiento x4 sobre la corona (lado derecho del disco)
    z = int(L * zoom / 2)
    cx, cy = int(L / 2 + 0.68 * C.DN / 2), L // 2
    za = cv2.resize(I_n[cy - z:cy + z, cx - z:cx + z], (lado // 2, lado // 2), interpolation=cv2.INTER_NEAREST)
    zb = cv2.resize(I_f[cy - z:cy + z, cx - z:cx + z], (lado // 2, lado // 2), interpolation=cv2.INTER_NEAREST)
    sep = np.full((lado, 8, 3), 255, np.uint8)
    col_a = np.vstack([za, np.full((lado - za.shape[0], za.shape[1], 3), 255, np.uint8)])
    col_b = np.vstack([zb, np.full((lado - zb.shape[0], zb.shape[1], 3), 255, np.uint8)])
    _texto(a, "Antes", (14, 32))
    _texto(b, "Despues", (14, 32))
    _texto(col_a, "x4", (10, 28), 0.6)
    _texto(col_b, "x4", (10, 28), 0.6)
    return a_rgb(np.hstack([a, sep, b, sep, col_a, sep, col_b]))


# ------------------------------------------------------------------ línea de referencia

def recta_en_radios(linea, fracciones):
    """Puntos (x, y) del disco enderezado donde la recta ajustada corta los círculos r = f·R.

    Se toma el corte hacia afuera (la recta apunta del centro al borde). Si la recta no
    alcanza ese radio (separación del centro mayor que r), el radio se omite.
    """
    c = C.LADO_N / 2.0
    R = C.DN / 2.0
    vx, vy, x0, y0 = linea["recta"]
    dx, dy = x0 - c, y0 - c
    b = vx * dx + vy * dy
    salida = []
    for f in fracciones:
        disc = b * b - (dx * dx + dy * dy - (f * R) ** 2)
        if disc < 0:
            continue
        t = -b + math.sqrt(disc)
        salida.append((f, x0 + t * vx, y0 + t * vy))
    return salida


# ------------------------------------------------------------------ mediciones

def polar_bandas(car):
    """Imagen polar horizontal (x = θ, y = r/R) con las bandas y marcas."""
    P = car["P"]                                # (ang, rad, 3)
    tira = np.ascontiguousarray(np.transpose(P, (1, 0, 2))[::-1])   # r crece hacia arriba
    H, W = tira.shape[:2]
    escala = 2
    tira = cv2.resize(tira, (W * escala // 1, H * escala), interpolation=cv2.INTER_NEAREST)
    H, W = tira.shape[:2]

    def y(f):
        return int(H - f * H)

    for (f0, f1), color in [(C.BANDA_MARCA, AZUL), (C.BANDA_MUESTREO, VERDE)]:
        capa = tira.copy()
        cv2.rectangle(capa, (0, y(f1)), (W - 1, y(f0)), _bgr(color), -1)
        tira = cv2.addWeighted(capa, 0.18, tira, 0.82, 0)
    for f in C.BANDA_CORONA:
        cv2.line(tira, (0, y(f)), (W, y(f)), (255, 255, 255), 1, cv2.LINE_AA)
    linea = car.get("linea")
    if linea is not None:
        # la recta ajustada vista en polar (si no pasa por el centro, se curva cerca de él)
        c = C.LADO_N / 2.0
        tramo, previo = [], None
        for f, xx, yy in recta_en_radios(linea, np.linspace(0.08, 1.0, 120)):
            th = math.degrees(math.atan2(-(yy - c), xx - c)) % 360.0
            q = (int(th / 360 * W), y(f))
            if previo is not None and abs(q[0] - previo[0]) > W / 2:   # cruce de 360° → 0°
                cv2.polylines(tira, [np.array(tramo, np.int32)], False, _bgr(AZUL), 2, cv2.LINE_AA)
                tramo = []
            tramo.append(q)
            previo = q
        if len(tramo) > 1:
            cv2.polylines(tira, [np.array(tramo, np.int32)], False, _bgr(AZUL), 2, cv2.LINE_AA)
        for pt in linea["puntos"]:
            q = (int(pt["theta"] / 360 * W), y(pt["r"]))
            relleno = (255, 255, 255) if pt["usado"] else (150, 150, 150)
            cv2.circle(tira, q, 6, relleno, -1, cv2.LINE_AA)
            cv2.circle(tira, q, 6, _bgr(AZUL), 2, cv2.LINE_AA)
    elif car["theta_ref"] is not None:
        x = int(car["theta_ref"] / 360 * W)
        cv2.line(tira, (x, 0), (x, H), _bgr(AZUL), 2, cv2.LINE_AA)
    return a_rgb(tira)


def perfil(car):
    """Gráfica de p(θ) con orificios, bloques azules, manchas y línea de referencia."""
    p = car["p"]
    th = np.arange(len(p)) * paso()
    fig, ax = plt.subplots(figsize=(10, 2.8), dpi=110)
    ax.fill_between(th, 0, 1, where=car["binario"] == 0, color="#e8ebf0", step="mid", lw=0,
                    label="orificio")
    ax.plot(th, p, color=TINTA, lw=1.2, label="material")
    ax.axhline(0.5, color=GRIS, lw=0.8, ls="--")
    for d in car["azules"]:
        ax.axvspan(d["theta"] - d["ancho"] / 2, d["theta"] + d["ancho"] / 2, color=AZUL, alpha=0.25, lw=0)
    for m in car["manchas"]:
        ax.axvline(m["theta"], color=ROJO, lw=1.6)
    if car["theta_ref"] is not None:
        ax.axvline(car["theta_ref"], color=AZUL, lw=2)
        ax.text(car["theta_ref"] + 2, 1.04, "línea de referencia", color=AZUL, fontsize=9)
    for h in car["huecos"]:
        ax.text(h["theta"], 0.06, str(h.get("num", "")), ha="center", fontsize=8, color=GRIS)
    ax.set_xlim(0, 360)
    ax.set_ylim(-0.02, 1.12)
    ax.set_xticks(range(0, 361, 30))
    ax.set_xlabel("ángulo desde la horizontal (°, antihorario)")
    ax.set_ylabel("1 = disco   0 = orificio")
    _estilo(ax)
    fig.tight_layout()
    return _fig_a_img(fig)


def espectro(car):
    """Espectro del perfil: la barra azul es la frecuencia dominante (k*)."""
    E = car["espectro"]
    k = np.arange(len(E))
    k1 = min(C.K_RANGO[1] + 2, len(E) - 1)
    ks = car["k_star"]
    fig, ax = plt.subplots(figsize=(5, 2.8), dpi=110)
    ax.axvspan(*C.K_RANGO, color="#eef0f6", lw=0, zorder=0)
    ax.vlines(k[1:k1 + 1], 0, E[1:k1 + 1], color=GRIS, lw=2)
    ax.vlines([ks], 0, [E[ks]], color=AZUL, lw=3.5)
    ax.axvline(ks, color=AZUL, lw=0.8, ls=":", zorder=0)
    ax.text(ks + 0.8, E[ks] * 0.97, f"Frecuencia: {ks}", color=AZUL, ha="left", va="top",
            fontsize=10, fontweight="bold")
    # marcas cada 4 y siempre la frecuencia dominante, resaltada
    marcas = sorted(set(range(0, k1 + 1, 4)) - {t for t in range(0, k1 + 1, 4) if abs(t - ks) < 2} | {ks})
    ax.set_xticks(marcas)
    for et in ax.get_xticklabels():
        if et.get_text() == str(ks):
            et.set_color(AZUL)
            et.set_fontweight("bold")
            et.set_fontsize(10)
    ax.set_xlim(0, k1 + 1)
    ax.set_ylim(0, E[1:k1 + 1].max() * 1.15)
    ax.set_xlabel("frecuencia (ciclos por vuelta)")
    ax.set_ylabel("magnitud")
    _estilo(ax)
    for et in ax.get_xticklabels():          # _estilo reasigna colores: se reaplica el resaltado
        if et.get_text() == str(ks):
            et.set_color(AZUL)
    fig.tight_layout()
    return _fig_a_img(fig)


def _estilo(ax):
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(GRIS)
    ax.tick_params(colors=TINTA, labelsize=8)
    ax.xaxis.label.set_color(TINTA)
    ax.yaxis.label.set_color(TINTA)


# ------------------------------------------------------------------ resultado

def anotada(I_f, car, cls):
    """Imagen final. Las etiquetas (1..N, S#, E#, M#) son las mismas del informe."""
    img = I_f.copy()
    L = C.LADO_N
    c = L / 2.0
    R = C.DN / 2.0
    R_ORIF = (13.0 / 29.8, 27.5 / 29.8)          # extensión radial de los orificios (fracción de R)

    def punto(theta, f):
        t = math.radians(theta)
        return int(c + f * R * math.cos(t)), int(c - f * R * math.sin(t))

    def rotulo(txt, theta, color, desde):
        """Etiqueta fuera del disco con una línea guía hasta el defecto."""
        x, y = punto(theta, 1.065)
        cv2.line(img, desde, (x, y), color, 2, cv2.LINE_AA)
        (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)
        x0 = min(max(x - tw // 2 - 7, 2), L - tw - 16)
        y0 = min(max(y - th // 2 - 7, 2), L - th - 16)
        cv2.rectangle(img, (x0, y0), (x0 + tw + 14, y0 + th + 14), color, -1, cv2.LINE_AA)
        cv2.putText(img, txt, (x0 + 7, y0 + th + 7), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (20, 20, 20), 2, cv2.LINE_AA)

    # sectores ausentes: arco azul en el borde + etiqueta S#
    for d in car["azules"]:
        cv2.ellipse(img, (int(c), int(c)), (int(0.97 * R), int(0.97 * R)), 0,
                    -(d["theta"] + d["ancho"] / 2), -(d["theta"] - d["ancho"] / 2), _bgr(AZUL), 14, cv2.LINE_AA)
        rotulo(d["etiqueta"], d["theta"], (235, 200, 160), punto(d["theta"], 0.99))

    # espacios con ancho incorrecto: recuadro amarillo ajustado al tramo + etiqueta E#
    for e in cls.get("espacios", []):
        angs = np.linspace(e["theta"] - e["ancho"] / 2, e["theta"] + e["ancho"] / 2, 12)
        pts = np.array([punto(a, f) for f in R_ORIF for a in angs], np.float32)
        caja = cv2.boxPoints(cv2.minAreaRect(pts)).astype(np.int32)
        cv2.polylines(img, [caja], True, _bgr(AMBAR_CLARO), 4, cv2.LINE_AA)
        rotulo(e["etiqueta"], e["theta"], _bgr(AMBAR_CLARO), punto(e["theta"], R_ORIF[1] + 0.02))

    # orificios numerados (1 = el primero después de la línea de referencia, antihorario)
    for h in car["huecos"]:
        x, y = punto(h["theta"], 0.685)
        cv2.circle(img, (x, y), 17, (30, 30, 30), -1, cv2.LINE_AA)
        cv2.circle(img, (x, y), 17, (255, 255, 255), 2, cv2.LINE_AA)
        t = str(h["num"])
        tw = cv2.getTextSize(t, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
        cv2.putText(img, t, (x - tw[0] // 2, y + tw[1] // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    (255, 255, 255), 2, cv2.LINE_AA)

    # manchas: recuadro rojo + etiqueta M#
    for m in car["manchas"]:
        x, y, w, h = m["bbox"]
        cv2.rectangle(img, (x - 4, y - 4), (x + w + 4, y + h + 4), _bgr(ROJO), 3, cv2.LINE_AA)
        txt = m["etiqueta"]
        (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)
        yy = y - 8 if y - th - 18 > 0 else y + h + th + 14
        cv2.rectangle(img, (x - 4, yy - th - 10), (x + tw + 10, yy + 5), _bgr(ROJO), -1, cv2.LINE_AA)
        cv2.putText(img, txt, (x + 3, yy - 2), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)

    # línea de referencia: recta ajustada a los puntos encontrados (blancos = usados)
    linea = car.get("linea")
    if linea is not None:
        tramo = recta_en_radios(linea, (0.1, 1.0))
        if len(tramo) == 2:
            (_, xa, ya), (_, xb, yb) = tramo
            cv2.line(img, (int(xa), int(ya)), (int(xb), int(yb)), _bgr(AZUL), 4, cv2.LINE_AA)
            fin = (int(xb), int(yb))
        else:
            fin = punto(car["theta_ref"], 1.0)
            cv2.line(img, punto(car["theta_ref"], 0.1), fin, _bgr(AZUL), 4, cv2.LINE_AA)
        rotulo("REF 0", car["theta_ref"], (235, 200, 160), fin)
        for pt in linea["puntos"]:          # encima de la etiqueta para que siempre se vean
            q = (int(round(pt["x"])), int(round(pt["y"])))
            relleno = (255, 255, 255) if pt["usado"] else (150, 150, 150)
            cv2.circle(img, q, 8, relleno, -1, cv2.LINE_AA)
            cv2.circle(img, q, 8, _bgr(AZUL), 3, cv2.LINE_AA)
    elif car["theta_ref"] is not None:
        cv2.line(img, punto(car["theta_ref"], 0.1), punto(car["theta_ref"], 1.0), _bgr(AZUL), 4, cv2.LINE_AA)
        rotulo("REF 0", car["theta_ref"], (235, 200, 160), punto(car["theta_ref"], 1.0))
    return a_rgb(img)


# ------------------------------------------------------------------ HTML

def tabla(filas, encabezado):
    """Tabla HTML con el estilo de la app."""
    th = "".join(f"<th>{h}</th>" for h in encabezado)
    tr = "".join("<tr>" + "".join(f"<td>{v}</td>" for v in f) + "</tr>" for f in filas)
    return f'<table class="ed-tabla"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>'


def tabla_validacion(val):
    filas = []
    for c in val["criterios"]:
        marca = '<span class="ed-ok">✓</span>' if c["ok"] else '<span class="ed-no">✗</span>'
        nombre = f'<b>{c["nombre"]}</b><div class="ed-desc">{c.get("descripcion", "")}</div>'
        filas.append([nombre, c["valor_txt"], c["umbral"], c["nivel"], marca])
    return tabla(filas, ["Qué se revisa", "Medido", "Aceptable", "Resultado", ""])
