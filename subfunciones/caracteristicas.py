"""
Bloque 6. Extracción de características sobre la imagen polar.

Convención angular: θ en grados, antihorario desde la horizontal (+x).
La fila j de la imagen polar P corresponde a θ = j · 360/POLAR_ANG.
"""
import math

import cv2
import numpy as np

from . import config as C
from .segmentacion import otsu_con_eta

# ------------------------------------------------------------------ utilidades

def paso():
    return 360.0 / C.POLAR_ANG


def cols(banda):
    return int(round(banda[0] * C.POLAR_RAD)), int(round(banda[1] * C.POLAR_RAD))


def tramos_ciclicos(b):
    """Tramos de valores iguales en un vector binario cíclico → [(valor, inicio, largo)]."""
    n = len(b)
    if np.all(b == b[0]):
        return [(int(b[0]), 0, n)]
    inicio = int(np.argmax(b != b[0]))          # arranca en un cambio
    r = np.roll(b, -inicio)
    cambios = np.flatnonzero(np.diff(r)) + 1
    bordes = np.concatenate([[0], cambios, [n]])
    return [(int(r[i0]), (i0 + inicio) % n, int(i1 - i0)) for i0, i1 in zip(bordes[:-1], bordes[1:])]


def quitar_tramos_cortos(b, minimo):
    """Histéresis: elimina (invierte) tramos menores a 'minimo' muestras, el más corto primero."""
    b = b.astype(np.uint8).copy()
    n = len(b)
    while True:
        t = tramos_ciclicos(b)
        if len(t) <= 1:
            return b
        v, i0, L = min(t, key=lambda x: x[2])
        if L >= minimo:
            return b
        idx = (np.arange(L) + i0) % n
        b[idx] = 1 - v


def centro_tramo(i0, L):
    return ((i0 + (L - 1) / 2.0) * paso()) % 360.0


def suavizado_circular(x, k):
    if k <= 1:
        return x
    ker = np.ones(k) / k
    pad = k // 2
    xx = np.concatenate([x[-pad:], x, x[:pad]])
    return np.convolve(xx, ker, mode="valid")[:len(x)]


def mad(x):
    return float(np.median(np.abs(x - np.median(x))))


def a_relativo(theta, theta_ref):
    if theta_ref is None:
        return None
    return (theta - theta_ref) % 360.0


# ------------------------------------------------------------------ 6.1 polar

def polar(I_f):
    """P (POLAR_ANG x POLAR_RAD x 3), filas en sentido antihorario."""
    c = C.LADO_N / 2.0
    P = cv2.warpPolar(I_f, (C.POLAR_RAD, C.POLAR_ANG), (c, c), C.DN / 2.0,
                      cv2.INTER_LINEAR | cv2.WARP_POLAR_LINEAR)
    # warpPolar: fila i ↔ ángulo de imagen (horario, y hacia abajo)
    # θ = (360 − θ_imagen) mod 360  → reordenar filas
    idx = (-np.arange(C.POLAR_ANG)) % C.POLAR_ANG
    return P[idx]


# ------------------------------------------------------------------ 6.3 marca

def azul(h, s, v=None, v_min=0):
    m = (h >= C.H_AZUL[0]) & (h <= C.H_AZUL[1]) & (s > C.S_MIN)
    return m & (v > v_min) if v is not None else m


def _puntaje_banda(P, banda):
    """Contraste relativo restringido a tono azul en una banda radial: z(θ) sin suavizar."""
    c0, c1 = cols(banda)
    sub = P[:, c0:c1]
    hsv = cv2.cvtColor(sub, cv2.COLOR_BGR2HSV)
    S = hsv[:, :, 1].astype(np.float64).mean(axis=1)
    V = hsv[:, :, 2].astype(np.float64).mean(axis=1)

    # tono de cada fila: color medio de la fila en la banda
    medio = sub.astype(np.float64).mean(axis=1).astype(np.uint8)[None]
    hsv_fila = cv2.cvtColor(medio, cv2.COLOR_BGR2HSV)[0]
    h_fila, s_fila = hsv_fila[:, 0].astype(int), hsv_fila[:, 1].astype(int)
    # mediana y MAD sin las filas rojas: una mancha en la banda infla el MAD y apaga la marca
    es_rojo = ((h_fila < C.H_ROJO[0]) | (h_fila > C.H_ROJO[1])) & (s_fila > C.S_ROJO / 2)
    # tono azul-violeta, o fila casi acromática (S baja: el tono no está definido)
    en_rango = (h_fila >= C.H_AZUL[0]) & (h_fila <= C.H_AZUL[1])
    es_azul = (en_rango | (s_fila < C.S_ACROMATICO)) & ~es_rojo
    ref = ~es_rojo if (~es_rojo).sum() > len(S) // 4 else np.ones_like(es_rojo)
    zS = (S - np.median(S[ref])) / max(mad(S[ref]), C.MAD_PISO)
    zV = (np.median(V[ref]) - V) / max(mad(V[ref]), C.MAD_PISO)
    return (np.maximum(zS, 0) + np.maximum(zV, 0)) * es_azul


def ajustar_linea(P, theta0):
    """Traza la línea de referencia con tres puntos y una recta ajustada.

    En cada banda de BANDAS_LINEA busca el máximo de z cerca de theta0, lo afina
    con una parábola y lo pasa al disco enderezado. Por los puntos con z ≥ Z_PUNTO_MIN
    ajusta una recta (cv2.fitLine) que no tiene que pasar por el centro. Con menos
    de dos puntos usa el rayo radial en theta0.
    """
    c = C.LADO_N / 2.0
    R = C.DN / 2.0
    n = C.POLAR_ANG
    j0 = int(round(theta0 / paso()))
    w = int(round(C.VENTANA_LINEA / paso()))
    puntos = []
    for banda in C.BANDAS_LINEA:
        z = suavizado_circular(_puntaje_banda(P, banda), 3)
        idx = np.arange(j0 - w, j0 + w + 1) % n
        k = int(np.argmax(z[idx]))
        j = idx[k]
        zm, za, zb = z[j], z[(j - 1) % n], z[(j + 1) % n]
        den = za - 2 * zm + zb
        delta = 0.5 * (za - zb) / den if den < 0 else 0.0
        theta = ((j + float(np.clip(delta, -0.5, 0.5))) * paso()) % 360.0
        r = (banda[0] + banda[1]) / 2.0
        t = math.radians(theta)
        puntos.append({"r": r, "theta": theta, "z": float(zm), "usado": bool(zm >= C.Z_PUNTO_MIN),
                       "x": c + r * R * math.cos(t), "y": c - r * R * math.sin(t)})

    usados = [q for q in puntos if q["usado"]]
    if len(usados) >= 2:
        pts = np.array([[q["x"], q["y"]] for q in usados], np.float32)
        vx, vy, x0, y0 = cv2.fitLine(pts, cv2.DIST_L2, 0, 0.01, 0.01).ravel()
        afuera = np.array([usados[-1]["x"] - usados[0]["x"], usados[-1]["y"] - usados[0]["y"]])
        if vx * afuera[0] + vy * afuera[1] < 0:
            vx, vy = -vx, -vy
        theta_ref = math.degrees(math.atan2(-vy, vx)) % 360.0
        # separación entre la recta y el centro del disco, en px de I_n (0 = línea radial)
        sep_px = abs((c - x0) * vy - (c - y0) * vx)
        metodo = f"recta por {len(usados)} puntos"
    else:
        t = math.radians(theta0)
        vx, vy, x0, y0 = math.cos(t), -math.sin(t), c, c
        theta_ref, sep_px = theta0, 0.0
        metodo = "radial (puntos insuficientes)"
    return {"theta": float(theta_ref), "puntos": puntos, "n_usados": len(usados),
            "recta": (float(vx), float(vy), float(x0), float(y0)),
            "separacion_px": float(sep_px), "metodo": metodo}   # px del disco enderezado (DN)


def buscar_marca(P):
    """Busca la línea de referencia.

    1) Ángulo inicial: contraste relativo en la banda de la marca (0,25 a 0,40 R),
       máximo de z(θ). Su puntaje z_marca decide si la marca es legible.
    2) Trazado: ajustar_linea() afina el ángulo con tres puntos (interior, intermedio
       y borde exterior) y una recta ajustada.
    """
    z = suavizado_circular(_puntaje_banda(P, C.BANDA_MARCA), C.SUAVIZADO_MARCA)
    j = int(np.argmax(z))
    zmax = float(z[j])
    encontrada = zmax >= C.Z_MIN
    linea = ajustar_linea(P, j * paso()) if encontrada else None
    return {"theta_ref": linea["theta"] if encontrada else None,
            "theta_cand": j * paso(), "linea": linea,
            "z": z, "z_marca": zmax, "encontrada": bool(encontrada)}


def marca_canny(P):
    """Alternativa descartada: ángulo de la marca con Canny y umbrales de Otsu. Se usa para comparar."""
    c0, c1 = cols(C.BANDA_MARCA)
    g = cv2.cvtColor(P[:, c0:c1], cv2.COLOR_BGR2GRAY)
    t, _ = otsu_con_eta(g)
    bordes = cv2.Canny(g, 0.5 * t, t)
    perfil = suavizado_circular(bordes.mean(axis=1), C.SUAVIZADO_MARCA)
    if perfil.max() == 0:
        return None
    return int(np.argmax(perfil)) * paso()


# ------------------------------------------------------------------ 6.4 perfil

def perfil_material(P):
    """Perfil p(θ): fracción de material en la banda de muestreo."""
    hsv = cv2.cvtColor(P, cv2.COLOR_BGR2HSV)
    S, V = hsv[:, :, 1], hsv[:, :, 2]
    k0, k1 = cols(C.BANDA_CORONA)
    t_c, eta_c = otsu_con_eta(V[:, k0:k1])
    # el color saturado (pintura, manchas) es material solo si hay brillo: en el fondo negro S es ruido
    v_color = C.V_COLOR_FRAC * t_c
    material = (V > t_c) | ((S > C.S_MIN) & (V > v_color))
    m0, m1 = cols(C.BANDA_MUESTREO)
    p = material[:, m0:m1].mean(axis=1)
    return p, material, t_c, eta_c


def contar(p):
    """Binariza p(θ) y separa los tramos en huecos y barras."""
    b = quitar_tramos_cortos((p > 0.5).astype(np.uint8), C.TRAMO_MIN)
    tr = tramos_ciclicos(b)
    huecos = [(i0, L) for v, i0, L in tr if v == 0]
    barras = [(i0, L) for v, i0, L in tr if v == 1]
    if len(tr) == 1:
        huecos = [] if tr[0][0] == 1 else huecos
    return b, huecos, barras


def espectro(p):
    """Magnitud de la DFT de p(θ) y frecuencia dominante k* dentro de K_RANGO."""
    E = np.abs(np.fft.rfft(p - p.mean()))
    k0, k1 = C.K_RANGO
    k1 = min(k1, len(E) - 1)
    k_star = int(k0 + np.argmax(E[k0:k1 + 1]))
    return E, k_star


def contar_componentes(I_f, t_c, v_color):
    """Alternativa a comparar: componentes conexas de la máscara de huecos en la
    corona (cartesiano). Da cantidad y ángulo de cada centroide, pero no da señal
    para la DFT y una mancha que cruza un hueco lo parte."""
    hsv = cv2.cvtColor(I_f, cv2.COLOR_BGR2HSV)
    S, V = hsv[:, :, 1], hsv[:, :, 2]
    L = C.LADO_N
    yy, xx = np.mgrid[:L, :L]
    r = np.hypot(xx - L / 2.0, yy - L / 2.0) / (C.DN / 2.0)
    corona = (r >= C.BANDA_MUESTREO[0]) & (r <= C.BANDA_MUESTREO[1])
    hueco = ~((V > t_c) | ((S > C.S_MIN) & (V > v_color))) & corona
    hueco = cv2.morphologyEx(hueco.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, _, st, cen = cv2.connectedComponentsWithStats(hueco, 8)
    area_min = 0.1 * np.median(st[1:, cv2.CC_STAT_AREA]) if n > 1 else 0
    angulos = [math.degrees(math.atan2(-(y - L / 2.0), x - L / 2.0)) % 360.0
               for i, (x, y) in enumerate(cen) if i > 0 and st[i, cv2.CC_STAT_AREA] > area_min]
    return len(angulos), sorted(angulos)


# ------------------------------------------------------------------ 6.5 azules

def bloques_azules(P, v_min=0):
    """Sectores tapados de azul en la banda de muestreo."""
    m0, m1 = cols(C.BANDA_MUESTREO)
    hsv = cv2.cvtColor(P[:, m0:m1], cv2.COLOR_BGR2HSV)
    frac = azul(hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2], v_min).mean(axis=1)
    b = (frac > C.FRAC_AZUL_FILA).astype(np.uint8)
    lista = []
    if b.any():
        for v, i0, L in tramos_ciclicos(b):
            if v == 1 and L * paso() > C.W_AZUL_MIN:
                lista.append({"theta": centro_tramo(i0, L), "ancho": L * paso(),
                              "i0": i0, "L": L})
    return lista, frac


# ------------------------------------------------------------------ 6.6 manchas

def manchas(I_f, mascara_disco, v_min=0):
    """Manchas rojas dentro del disco con área mayor que A_MIN."""
    hsv = cv2.cvtColor(I_f, cv2.COLOR_BGR2HSV)
    H, S, V = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    rojo = (((H < C.H_ROJO[0]) | (H > C.H_ROJO[1])) & (S > C.S_ROJO) & (V > v_min)
            & (mascara_disco > 0))
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (C.KERNEL_MANCHA, C.KERNEL_MANCHA))
    rojo = cv2.morphologyEx(rojo.astype(np.uint8) * 255, cv2.MORPH_OPEN, k)
    n, lab, st, cen = cv2.connectedComponentsWithStats(rojo, 8)
    area_disco = math.pi * (C.DN / 2.0) ** 2
    c = C.LADO_N / 2.0
    lista = []
    for i in range(1, n):
        pct = 100.0 * st[i, cv2.CC_STAT_AREA] / area_disco
        if pct <= C.A_MIN:
            continue
        x, y = cen[i]
        th = math.degrees(math.atan2(-(y - c), x - c)) % 360.0
        lista.append({"theta": th, "area_pct": pct, "r": math.hypot(x - c, y - c) / (C.DN / 2.0),
                      "x": float(x), "y": float(y), "bbox": [int(v) for v in st[i, :4]]})
    lista.sort(key=lambda d: -d["area_pct"])
    return lista, rojo


# ------------------------------------------------------------------ 6.7 vector

def extraer(I_f, mascara_disco=None, marca=None, P=None):
    """Vector de características del bloque 6."""
    if mascara_disco is None:
        mascara_disco = np.zeros(I_f.shape[:2], np.uint8)
        cv2.circle(mascara_disco, (C.LADO_N // 2,) * 2, C.DN // 2, 255, -1)
    P = polar(I_f) if P is None else P
    marca = marca or buscar_marca(P)
    th_ref = marca["theta_ref"]

    p, material, t_c, eta_c = perfil_material(P)
    b, huecos, barras = contar(p)
    E, k_star = espectro(p)
    v_color = C.V_COLOR_FRAC * t_c
    azules, frac_azul = bloques_azules(P, v_color)
    lista_manchas, mascara_roja = manchas(I_f, mascara_disco, v_color)

    def info(tr):
        return [{"theta": centro_tramo(i0, L), "ancho": L * paso(), "i0": i0, "L": L,
                 "rel": a_relativo(centro_tramo(i0, L), th_ref)} for i0, L in tr]

    lh, lb = info(huecos), info(barras)
    for d in azules + lista_manchas:
        d["rel"] = a_relativo(d["theta"], th_ref)

    # numeración única (la misma en la imagen anotada y en el informe):
    # orificios 1..N antihorario desde la marca; S1.. sectores ausentes; M1.. manchas (de mayor a menor)
    def clave(d):
        return d["rel"] if d["rel"] is not None else d["theta"]
    for i, h in enumerate(sorted(lh, key=clave), 1):
        h["num"] = i
    for i, barra in enumerate(sorted(lb, key=clave), 1):
        barra["num"] = i
    for i, d in enumerate(sorted(azules, key=clave), 1):
        d["etiqueta"] = f"S{i}"
    for i, m in enumerate(lista_manchas, 1):
        m["etiqueta"] = f"M{i}"

    return {
        "P": P, "p": p, "binario": b, "material": material, "t_c": t_c,
        "espectro": E, "k_star": k_star,
        "N": len(lh), "huecos": lh, "barras": lb,
        "w_h": [d["ancho"] for d in lh], "w_b": [d["ancho"] for d in lb],
        "N_azul": len(azules), "azules": azules, "frac_azul": frac_azul,
        "theta_ref": th_ref, "z_marca": marca["z_marca"], "z": marca["z"], "marca": marca,
        "linea": marca.get("linea"),
        "manchas": lista_manchas, "mascara_roja": mascara_roja,
    }
