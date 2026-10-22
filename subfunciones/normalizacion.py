"""
Bloque 3. Normalización geométrica (desde I0).

Una afín estira el eje menor por a/b (elipse → círculo), escala a DN y
centra en (LADO_N/2, LADO_N/2). Si hay que reducir, primero se aplica
INTER_AREA al recorte porque warpAffine no lo admite.
"""
import math

import cv2
import numpy as np

from . import config as C


def matriz_afin(xc, yc, a, b, phi_deg, k):
    """M (2x3) que lleva la elipse (xc,yc,a,b,phi) a un círculo de radio k·a centrado en el origen."""
    p = math.radians(phi_deg)
    v = np.array([-math.sin(p), math.cos(p)])           # dirección del eje menor
    A = np.eye(2) + (a / b - 1.0) * np.outer(v, v)       # estira solo el eje menor
    A = k * A
    t = -A @ np.array([xc, yc])
    return np.hstack([A, t[:, None]])


def normalizar(I0, geo):
    """Endereza el disco y lo deja con diámetro DN en una imagen de LADO_N × LADO_N."""
    L = C.LADO_N
    c = L / 2.0
    xc, yc, a, b, phi = geo["xc"], geo["yc"], geo["a"], geo["b"], geo["phi"]
    k = C.DN / (2.0 * a)

    # recorte holgado alrededor del disco (rapidez con imágenes de 15 MP)
    H, W = I0.shape[:2]
    m = a * (L / C.DN) * 1.05 * max(1.0, a / b)
    x0, x1 = int(max(0, xc - m)), int(min(W, xc + m + 1))
    y0, y1 = int(max(0, yc - m)), int(min(H, yc + m + 1))
    rec = I0[y0:y1, x0:x1]
    xr, yr = xc - x0, yc - y0

    if k < 1.0:
        # reducción con promediado: primero INTER_AREA, luego la afín sin escala extra
        hr, wr = rec.shape[:2]
        nw, nh = max(1, round(wr * k)), max(1, round(hr * k))
        rec = cv2.resize(rec, (nw, nh), interpolation=cv2.INTER_AREA)
        kx, ky = nw / wr, nh / hr
        xr, yr = xr * kx, yr * ky
        a2, b2 = a * k, b * k
        M = matriz_afin(xr, yr, a2, b2, phi, C.DN / (2.0 * a2))
    else:
        M = matriz_afin(xr, yr, a, b, phi, k)
    M[:, 2] += c

    I_n = cv2.warpAffine(rec, M, (L, L), flags=cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))
    mascara = np.zeros((L, L), np.uint8)
    cv2.circle(mascara, (int(c), int(c)), C.DN // 2, 255, -1)
    return {"I_n": I_n, "mascara_disco": mascara, "escala": k}
