"""Bloque 1. Adquisición: foto JPG o PNG → I0 (original) e I_loc (reducida)."""
import os

import cv2
import numpy as np

from . import config as C

EXTENSIONES = (".jpg", ".jpeg", ".png")


def leer(ruta):
    """Lee una foto JPG o PNG. Devuelve BGR uint8 a resolución original."""
    ext = os.path.splitext(ruta)[1].lower()
    if ext not in EXTENSIONES:
        raise ValueError(f"Formato no admitido ({ext or 'sin extensión'}). Solo se aceptan fotos JPG o PNG.")
    # imdecode admite rutas con tildes en Windows (cv2.imread no siempre)
    datos = np.fromfile(ruta, dtype=np.uint8)
    img = cv2.imdecode(datos, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"No se pudo leer la imagen: {os.path.basename(ruta)}")
    return img


def reducir(I0, lado=None):
    """Reduce a 'lado' px de lado largo con INTER_AREA. Devuelve (I_loc, s)."""
    lado = lado or C.LADO_LOC
    h, w = I0.shape[:2]
    s = lado / max(w, h)
    if s >= 1.0:
        return I0.copy(), 1.0
    I_loc = cv2.resize(I0, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA)
    return I_loc, s


def cargar(ruta):
    """Lee la foto y prepara la versión reducida para localizar el disco."""
    I0 = leer(ruta)
    I_loc, s = reducir(I0)
    return {"I0": I0, "I_loc": I_loc, "s": s, "ruta": ruta,
            "nombre": os.path.basename(ruta)}
