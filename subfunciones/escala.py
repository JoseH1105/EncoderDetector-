"""
Escala de referencia: diámetro aparente del disco.

El tamaño que se reporta no es el real de la pieza sino el aparente en la foto.
Se toma una foto de referencia, a la distancia estándar, en la que el disco mide
REF_DIAMETRO_MM (59,5 mm). Su diámetro en píxeles fija la escala:

    px_por_mm = D_referencia [px] / 59,5 mm

y en cualquier otra foto:

    diámetro aparente [mm] = D0 [px] / px_por_mm

Si el disco está más cerca que en la referencia se ve más grande, y más lejos,
más pequeño. Todo se lleva a píxeles de la resolución nativa de la cámara
(ANCHO_NATIVO × ALTO_NATIVO): una imagen con la misma proporción y otro ancho se
toma como reducida y se reescala; una con otra proporción se toma como recorte
(los píxeles valen lo mismo que en la nativa).

La medición de la referencia se guarda en datos/referencia_escala.json y se
rehace sola si cambia la imagen de referencia.
"""
import json
import os

from . import config as C

RUTA_JSON = os.path.join(C.DIR_DATOS, "referencia_escala.json")
_cache = None


def a_nativo(d_px, ancho, alto):
    """Lleva una longitud en px de una imagen de ancho×alto a px de la resolución nativa.
    Devuelve (d_nativo, reescalada)."""
    aspecto = ancho / alto if alto else 0
    nativo = C.ANCHO_NATIVO / C.ALTO_NATIVO
    if abs(aspecto - nativo) / nativo < C.TOLERANCIA_ASPECTO and ancho != C.ANCHO_NATIVO:
        return d_px * C.ANCHO_NATIVO / ancho, True
    return d_px, False


def _firma(ruta):
    st = os.stat(ruta)
    return {"bytes": st.st_size, "mtime": int(st.st_mtime)}


def medir_referencia(ruta=None):
    """Localiza el disco en la foto de referencia y calcula px_por_mm (en px nativos)."""
    from . import adquisicion, segmentacion
    ruta = ruta or os.path.join(C.DIR_DATOS, C.REF_IMAGEN)
    adq = adquisicion.cargar(ruta)
    geo = segmentacion.localizar(adq["I_loc"], adq["s"])
    if not geo["ok"]:
        raise ValueError(f"No se encontró el disco en la imagen de referencia {os.path.basename(ruta)}")
    alto, ancho = adq["I0"].shape[:2]
    d_nat, reesc = a_nativo(geo["D0"], ancho, alto)
    ref = {"archivo": os.path.basename(ruta), **_firma(ruta), "ancho": ancho, "alto": alto,
           "D_px": round(geo["D0"], 2), "D_px_nativo": round(d_nat, 2), "reescalada": reesc,
           "diametro_mm": C.REF_DIAMETRO_MM, "px_por_mm": round(d_nat / C.REF_DIAMETRO_MM, 4)}
    try:
        with open(RUTA_JSON, "w", encoding="utf-8") as f:
            json.dump(ref, f, indent=2, ensure_ascii=False)
    except OSError:
        pass                                   # sin permiso de escritura: se usa en memoria
    return ref


def referencia():
    """Medición de la referencia (en caché; se rehace si cambió la imagen)."""
    global _cache
    ruta = os.path.join(C.DIR_DATOS, C.REF_IMAGEN)
    if _cache is not None:
        return _cache
    if os.path.exists(RUTA_JSON) and os.path.exists(ruta):
        with open(RUTA_JSON, encoding="utf-8") as f:
            ref = json.load(f)
        if ref.get("archivo") == C.REF_IMAGEN and {k: ref.get(k) for k in ("bytes", "mtime")} == _firma(ruta):
            _cache = ref
            return ref
    if not os.path.exists(ruta):
        return None
    _cache = medir_referencia(ruta)
    return _cache


def diametro_aparente(d0_px, forma):
    """Diámetro del disco en la foto: px medidos, px nativos y mm aparentes según la referencia."""
    alto, ancho = forma[:2]
    d_nat, reesc = a_nativo(d0_px, ancho, alto)
    ref = referencia()
    mm = d_nat / ref["px_por_mm"] if ref else None
    return {"D_px": d0_px, "D_px_nativo": d_nat, "reescalada": reesc, "mm": mm,
            "px_por_mm": ref["px_por_mm"] if ref else None, "ancho": ancho, "alto": alto}
