"""
Bloque 2. Segmentación y localización (sobre I_loc).

Canal V → Otsu (+η) → apertura y cierre → contornos externos →
candidato de mayor circularidad → fitEllipse → coordenadas de I0.
"""
import math

import cv2
import numpy as np

from . import config as C


def otsu_con_eta(canal, mascara=None):
    """Umbral de Otsu y separabilidad η = σ²_B / σ²_T (0..1)."""
    datos = canal[mascara > 0] if mascara is not None else canal.ravel()
    hist = np.bincount(datos.ravel(), minlength=256).astype(np.float64)
    p = hist / max(hist.sum(), 1)
    niveles = np.arange(256)
    w0 = np.cumsum(p)
    mu = np.cumsum(p * niveles)
    mu_t = mu[-1]
    var_t = float(np.sum(p * (niveles - mu_t) ** 2))
    with np.errstate(divide="ignore", invalid="ignore"):
        var_b = (mu_t * w0 - mu) ** 2 / (w0 * (1 - w0))
    var_b = np.nan_to_num(var_b)
    t = int(np.argmax(var_b))
    eta = float(var_b[t] / var_t) if var_t > 0 else 0.0
    return t, eta


def localizar(I_loc, s):
    """Encuentra el disco en I_loc y devuelve su elipse en coordenadas de I0."""
    hsv = cv2.cvtColor(I_loc, cv2.COLOR_BGR2HSV)
    V = hsv[:, :, 2]
    t, eta = otsu_con_eta(V)
    mascara = (V > t).astype(np.uint8) * 255

    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (C.KERNEL_MORF, C.KERNEL_MORF))
    mascara = cv2.morphologyEx(mascara, cv2.MORPH_OPEN, k)
    mascara = cv2.morphologyEx(mascara, cv2.MORPH_CLOSE, k)

    contornos, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    h, w = V.shape
    area_min = C.AREA_MIN_CONTORNO * h * w

    mejor, C_mejor = None, -1.0
    for c in contornos:
        A = cv2.contourArea(c)
        if A < area_min or len(c) < 5:
            continue
        P = cv2.arcLength(c, True)
        circ = 4 * math.pi * A / (P * P) if P > 0 else 0.0
        if circ > C_mejor:
            mejor, C_mejor = c, circ

    base = {"ok": False, "C": max(C_mejor, 0.0), "eta": eta, "umbral_V": t,
            "mascara": mascara, "s": s, "forma_loc": (h, w)}
    if mejor is None or C_mejor < C.C_MIN:
        base["motivo"] = "No se encontró un contorno circular (disco ausente o ilegible)"
        return base

    (cx, cy), (d1, d2), ang = cv2.fitEllipse(mejor)
    # semieje mayor a y su dirección phi (grados, sentido de la imagen)
    if d1 >= d2:
        a_loc, b_loc, phi = d1 / 2, d2 / 2, ang
    else:
        a_loc, b_loc, phi = d2 / 2, d1 / 2, ang + 90.0
    phi = phi % 180.0

    # ¿la elipse cabe completa en el encuadre? (caja envolvente exacta)
    pr = math.radians(phi)
    ex = math.sqrt((a_loc * math.cos(pr)) ** 2 + (b_loc * math.sin(pr)) ** 2)
    ey = math.sqrt((a_loc * math.sin(pr)) ** 2 + (b_loc * math.cos(pr)) ** 2)
    m = C.MARGEN_BORDE
    completo = (cx - ex >= m and cy - ey >= m and cx + ex <= w - 1 - m and cy + ey <= h - 1 - m)

    a, b = a_loc / s, b_loc / s
    D0 = 2 * a
    relleno = np.zeros_like(mascara)
    cv2.drawContours(relleno, [mejor], -1, 255, -1)
    base.update({
        "ok": True, "motivo": "",
        "xc": cx / s, "yc": cy / s, "a": a, "b": b, "phi": phi,
        "D0": D0,
        "razon_ba": b / a,
        "inclinacion": math.degrees(math.acos(min(1.0, b / a))),
        "completo": bool(completo),
        "contorno_loc": mejor, "mascara_disco_loc": relleno,
    })
    return base


def localizar_hough(I_loc, s):
    """Alternativa a comparar (supone círculo, falla con inclinación)."""
    V = cv2.cvtColor(I_loc, cv2.COLOR_BGR2HSV)[:, :, 2]
    V = cv2.medianBlur(V, 5)
    h, w = V.shape
    circ = cv2.HoughCircles(V, cv2.HOUGH_GRADIENT, dp=1.5, minDist=min(h, w),
                            param1=120, param2=40,
                            minRadius=int(0.03 * min(h, w)), maxRadius=int(0.5 * min(h, w)))
    if circ is None:
        return {"ok": False}
    x, y, r = circ[0, 0]
    return {"ok": True, "xc": x / s, "yc": y / s, "a": r / s, "b": r / s, "D0": 2 * r / s}
