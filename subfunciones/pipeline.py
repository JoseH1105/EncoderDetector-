"""
Encadena los bloques 1 a 7.

- ejecutar(ruta): generador para la app → (etapa, resultados)
- analizar(ruta): corre todo y devuelve un dict (lotes y calibración)
- medir(ruta):    bloques 1 a 6 sin decidir, solo números (calibrar.py)
"""
import math
import time

import cv2

from . import (adquisicion, caracteristicas, clasificacion, escala, normalizacion, ruido,
               segmentacion, validacion)
from . import config as C


def ejecutar(ruta, filtro=None):
    """Generador por etapas. Si la validación falla se detiene ahí."""
    t0 = time.time()
    r = {"tiempos": {}}

    adq = adquisicion.cargar(ruta)
    r["adq"] = adq
    geo = segmentacion.localizar(adq["I_loc"], adq["s"])
    if geo["ok"]:
        geo["aparente"] = escala.diametro_aparente(geo["D0"], adq["I0"].shape)
    r["geo"] = geo
    r["tiempos"]["segmentacion"] = time.time() - t0
    yield "segmentacion", r

    if not geo["ok"]:
        r["val"] = validacion.evaluar(geo)
        r["cls"] = clasificacion.clasificar(None, r["val"])
        yield "validacion", r
        return

    t = time.time()
    nor = normalizacion.normalizar(adq["I0"], geo)
    rui = ruido.procesar(nor["I_n"], nor["mascara_disco"], filtro=filtro)
    r["nor"], r["rui"] = nor, rui
    r["tiempos"]["ruido"] = time.time() - t
    yield "ruido", r

    t = time.time()
    P = caracteristicas.polar(rui["I_f"])
    marca = caracteristicas.buscar_marca(P)
    val = validacion.evaluar(geo, rui["I_f"], marca, nor["mascara_disco"])
    r["P"], r["marca"], r["val"] = P, marca, val
    r["tiempos"]["validacion"] = time.time() - t
    if not val["pasa"]:
        r["cls"] = clasificacion.clasificar(None, val)
        yield "validacion", r
        return
    yield "validacion", r

    t = time.time()
    car = caracteristicas.extraer(rui["I_f"], nor["mascara_disco"], marca, P)
    r["car"] = car
    r["tiempos"]["caracteristicas"] = time.time() - t
    yield "caracteristicas", r

    r["cls"] = clasificacion.clasificar(car, val)
    r["tiempos"]["total"] = time.time() - t0
    yield "resultado", r


def analizar(ruta, filtro=None):
    """Corre el sistema completo y devuelve el resultado final."""
    r = None
    for _, r in ejecutar(ruta, filtro):
        pass
    return r


def medir(ruta, filtro=None):
    """Bloques 1 a 6 sin decidir: todas las métricas en un dict plano."""
    adq = adquisicion.cargar(ruta)
    geo = segmentacion.localizar(adq["I_loc"], adq["s"])
    fila = {"C": geo["C"], "eta": geo["eta"], "seg_ok": geo["ok"]}
    if not geo["ok"]:
        return fila
    nor = normalizacion.normalizar(adq["I0"], geo)
    rui = ruido.procesar(nor["I_n"], nor["mascara_disco"], filtro=filtro)
    I_f, m = rui["I_f"], nor["mascara_disco"]
    P = caracteristicas.polar(I_f)
    marca = caracteristicas.buscar_marca(P)
    car = caracteristicas.extraer(I_f, m, marca, P)
    th_canny = caracteristicas.marca_canny(P)
    ap = escala.diametro_aparente(geo["D0"], adq["I0"].shape)
    fila.update({
        "D0": geo["D0"], "D0_nativo": ap["D_px_nativo"], "diametro_aparente_mm": ap["mm"],
        "razon_ba": geo["razon_ba"],
        "inclinacion": geo["inclinacion"], "completo": geo["completo"],
        "sigma": rui["sigma"], "F": validacion.enfoque(I_f, m),
        "sat_marca": validacion.saturacion_banda_marca(I_f),
        "z_marca": marca["z_marca"], "theta_marca": marca["theta_cand"],
        "theta_canny": th_canny,
        "N": car["N"], "k_star": car["k_star"], "N_azul": car["N_azul"],
        "azules_ancho": ";".join(f"{d['ancho']:.1f}" for d in car["azules"]),
        "w_h": ";".join(f"{w:.1f}" for w in car["w_h"]),
        "w_b": ";".join(f"{w:.1f}" for w in car["w_b"]),
        "n_manchas": len(car["manchas"]),
        "area_manchas": ";".join(f"{d['area_pct']:.3f}" for d in car["manchas"]),
        "area_roja_max": _area_roja_max(car), "t_c": car["t_c"],
        "N_componentes": caracteristicas.contar_componentes(
            I_f, car["t_c"], C.V_COLOR_FRAC * car["t_c"])[0],
    })
    return fila


def _area_roja_max(car):
    """Mayor componente roja (sin filtro A_MIN) en % del disco. Sirve para fijar A_MIN."""
    n, _, st, _ = cv2.connectedComponentsWithStats(car["mascara_roja"], 8)
    if n <= 1:
        return 0.0
    return float(100.0 * st[1:, cv2.CC_STAT_AREA].max() / (math.pi * (C.DN / 2) ** 2))
