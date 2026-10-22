"""
Bloque 5. Validación.

Revisa si la foto sirve para diagnosticar. Las medidas de imagen se toman
sobre I_f y las geométricas vienen del bloque 2. Cada criterio guarda nombre,
valor, umbral, nivel y si pasa; los que fallan agregan su motivo.
"""
import math

import cv2
import numpy as np

from . import config as C


def enfoque(I_f, mascara):
    """F = Var(∇²I) / (p95 − p5)² × 10³ dentro del disco (normalizado por contraste).

    Se mide sobre I_f reducida a ESCALA_ENFOQUE, así F responde al ancho del
    borde y no al grano de la imagen.
    """
    g = cv2.cvtColor(I_f, cv2.COLOR_BGR2GRAY)
    e = C.ESCALA_ENFOQUE
    if e != 1.0:
        g = cv2.resize(g, None, fx=e, fy=e, interpolation=cv2.INTER_AREA)
        mascara = cv2.resize(mascara, None, fx=e, fy=e, interpolation=cv2.INTER_NEAREST)
    zona = cv2.erode(mascara, np.ones((3, 3), np.uint8)) > 0
    lap = cv2.Laplacian(g.astype(np.float64), cv2.CV_64F, ksize=1)
    p5, p95 = np.percentile(g[zona], [5, 95])
    rango = max(float(p95 - p5), 1.0)
    return float(lap[zona].var() / rango ** 2 * 1e3)


def saturacion_banda_marca(I_f):
    """% de píxeles recortados (los 3 canales ≥ NIVEL_SATURADO) en la banda de la marca."""
    L = C.LADO_N
    yy, xx = np.mgrid[:L, :L]
    r = np.hypot(xx - L / 2.0, yy - L / 2.0) / (C.DN / 2.0)
    banda = (r >= C.BANDA_MARCA[0]) & (r <= C.BANDA_MARCA[1])
    minimo = I_f.min(axis=2)
    return float(100.0 * (minimo[banda] >= C.NIVEL_SATURADO).mean())


def _nivel(valor, cortes, nombres, mayor_es_mejor=True):
    """cortes ascendentes; nombres de peor a mejor si mayor_es_mejor."""
    i = int(np.searchsorted(cortes, valor, side="right"))
    return nombres[i] if mayor_es_mejor else nombres[len(nombres) - 1 - i]


def evaluar(geo, I_f=None, marca=None, mascara=None):
    """Evalúa los criterios de calidad. Sin I_f solo revisa la geometría."""
    crit = []

    def agregar(nombre, descripcion, valor, umbral, nivel, ok, motivo, fmt="{:.2f}"):
        crit.append({"nombre": nombre, "descripcion": descripcion, "valor": valor,
                     "valor_txt": fmt.format(valor) if isinstance(valor, (int, float)) else str(valor),
                     "umbral": umbral, "nivel": nivel, "ok": bool(ok),
                     "motivo": "" if ok else motivo})

    agregar("Disco encontrado",
            "Hay un contorno redondo que puede ser el disco. Se mide su redondez (1 = círculo perfecto).",
            geo.get("C", 0.0), f"redondez ≥ {C.C_MIN}",
            "sí" if geo.get("ok") else "no", geo.get("ok", False),
            geo.get("motivo") or "No se encontró un disco en la imagen")
    if not geo.get("ok"):
        return _cerrar(crit)

    agregar("Disco completo",
            "El disco entero aparece en la foto, sin quedar cortado por el borde.",
            "sí" if geo["completo"] else "no", "dentro de la foto",
            "completo" if geo["completo"] else "cortado", geo["completo"],
            "El disco queda cortado por el borde de la foto")

    agregar("Tamaño del disco en la foto",
            "Diámetro en píxeles. Si es muy pequeño la línea de referencia no se alcanza a ver.",
            geo["D0"], f"≥ {C.D_MIN} px",
            "suficiente" if geo["D0"] >= C.D_MIN else "muy pequeño",
            geo["D0"] >= C.D_MIN, "El disco se ve demasiado pequeño en la foto", "{:.0f} px")

    th = geo["inclinacion"]
    lim = math.cos(math.radians(C.THETA_MAX))
    agregar("Inclinación",
            "Qué tan ladeado está el disco respecto a la cámara. 0° = cámara justo encima.",
            th, f"≤ {C.THETA_MAX:.0f}°",
            _nivel(th, [C.THETA_MEDIA, C.THETA_MAX], ["excesiva", "media", "baja"], False),
            geo["razon_ba"] >= lim, "El disco está demasiado inclinado respecto a la cámara", "{:.1f}°")

    if I_f is None:
        return _cerrar(crit)

    F = enfoque(I_f, mascara)
    agregar("Nitidez",
            "Qué tan definidos se ven los bordes de los orificios. Bajo = foto desenfocada.",
            F, f"≥ {C.F_MIN:.2f}",
            _nivel(F, [C.F_MIN, C.F_BUENO], ["insuficiente", "aceptable", "buena"]),
            F >= C.F_MIN, "La foto está desenfocada", "{:.2f}")

    sat = saturacion_banda_marca(I_f)
    agregar("Zona de la línea quemada",
            "Porcentaje de la zona de la línea azul que quedó blanco puro por exceso de luz.",
            sat, f"≤ {C.SAT_MARCA_MAX:.0f} %",
            _nivel(sat, [C.SAT_MARCA_ALTA, C.SAT_MARCA_MAX], ["sobreexpuesta", "alta", "correcta"], False),
            sat <= C.SAT_MARCA_MAX, "Hay demasiada luz en la zona de la línea de referencia", "{:.0f} %")

    eta = geo["eta"]
    agregar("Contraste disco y fondo",
            "Qué tan bien se separa el disco blanco del fondo oscuro (1 = separación perfecta).",
            eta, f"≥ {C.ETA_MIN}",
            _nivel(eta, [C.ETA_MIN, C.ETA_ALTO], ["bajo", "medio", "alto"]),
            eta >= C.ETA_MIN, "El disco no se distingue bien del fondo", "{:.2f}")

    if marca is not None:
        z = marca["z_marca"]
        agregar("Línea de referencia visible",
                "Qué tanto resalta la línea azul sobre el disco. Bajo = no se encuentra.",
                z, f"≥ {C.Z_MIN:.1f}",
                "visible" if z >= C.Z_MIN else "no encontrada",
                z >= C.Z_MIN, "No se encontró la línea azul de referencia", "{:.1f}")
    return _cerrar(crit)


def _cerrar(crit):
    motivos = [c["motivo"] for c in crit if not c["ok"]]
    return {"pasa": len(motivos) == 0, "criterios": crit, "motivos": motivos}
