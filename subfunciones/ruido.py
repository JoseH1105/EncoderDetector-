"""
Bloque 4. Diagnóstico y reducción de ruido (sobre I_n).

σ̂ se estima con el método de Immerkaer (Laplaciano 3x3) dentro del disco,
sin los píxeles de gradiente alto (percentil GRAD_EXCLUIR_PCT), que son bordes
de huecos y contorno. El gradiente se mide sobre la imagen suavizada. Según σ̂
se aplica un filtro bilateral autoajustado, un gaussiano (alternativa) o ninguno.
"""
import math

import cv2
import numpy as np

from . import config as C

_N = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], np.float64)


def sigma_immerkaer(gris, mascara):
    """σ̂ del ruido dentro del disco, sin los bordes."""
    g = gris.astype(np.float64)
    resp = np.abs(cv2.filter2D(g, cv2.CV_64F, _N, borderType=cv2.BORDER_REFLECT))
    zona = cv2.erode(mascara, np.ones((7, 7), np.uint8)) > 0
    suave = cv2.GaussianBlur(g, (0, 0), 2.0)
    gx = cv2.Sobel(suave, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(suave, cv2.CV_64F, 0, 1, ksize=3)
    mag = np.hypot(gx, gy)
    corte = np.percentile(mag[zona], C.GRAD_EXCLUIR_PCT)
    plano = cv2.dilate((mag > corte).astype(np.uint8), np.ones((5, 5), np.uint8)) == 0
    sel = zona & plano
    if sel.sum() < 1000:
        sel = zona
    return float(math.sqrt(math.pi / 2) * resp[sel].mean() / 6.0)


def nivel_ruido(sigma):
    if sigma <= C.SIGMA_CAMARA:
        return "bajo"
    return "medio" if sigma <= C.SIGMA_ALTO else "alto"


def procesar(I_n, mascara, filtro=None):
    """Mide el ruido de I_n y lo filtra si σ̂ supera SIGMA_CAMARA."""
    filtro = filtro or C.FILTRO
    gris = cv2.cvtColor(I_n, cv2.COLOR_BGR2GRAY)
    sigma = sigma_immerkaer(gris, mascara)
    nivel = nivel_ruido(sigma)

    if sigma <= C.SIGMA_CAMARA:
        I_f, nombre, params = I_n.copy(), "ninguno", {}
    elif filtro == "gaussiano":
        sg = max(0.3, C.K_GAUSS * sigma)
        I_f = cv2.GaussianBlur(I_n, (0, 0), sg)
        nombre, params = "gaussiano", {"sigma": round(sg, 2)}
    else:
        sc = C.K_BILATERAL * sigma
        I_f = cv2.bilateralFilter(I_n, C.D_BILATERAL, sc, C.SIGMA_ESPACIO)
        nombre, params = "bilateral", {"d": C.D_BILATERAL, "sigma_color": round(sc, 2),
                                       "sigma_espacio": C.SIGMA_ESPACIO}
    return {"I_f": I_f, "sigma": sigma, "nivel": nivel, "filtro": nombre, "params": params}
