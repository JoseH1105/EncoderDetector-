"""Bloque 7. Clasificación (eje A: patrón, eje B: manchas) y veredicto.

Cada defecto lleva una etiqueta que también aparece dibujada en la imagen
anotada, para que el informe y la imagen se puedan cruzar:
  S1, S2…  sector ausente (orificio tapado de azul)
  E1, E2…  espacio con ancho incorrecto (orificio o barra fuera de tolerancia)
  M1, M2…  mancha roja
"""
from . import config as C

NOMBRES_A = {"A0": "Correcto", "A1": "Sector ausente", "A2": "Anchura incorrecta",
             "A3": "Sector añadido", "A9": "Patrón no reconocido"}
NOMBRES_B = {"B0": "Sin defecto local", "B1": "Mancha"}

# nombres para la interfaz (sin códigos)
SENCILLO_A = {"A0": "Patrón correcto", "A1": "Sector ausente", "A2": "Ancho incorrecto",
              "A3": "Sector añadido", "A9": "Patrón no reconocido"}
SENCILLO_B = {"B0": "Sin manchas", "B1": "Manchas rojas"}


def _donde(d):
    r = d.get("rel")
    if r is None:
        return f"a {d['theta']:.0f}° desde la horizontal"
    return f"a {r:.0f}° de la línea de referencia"


def _vecino_de_azul(h, azules):
    """El tramo toca un bloque azul (sector ausente): su borde lo define la pintura,
    no el corte, así que su ancho no se compara con la tolerancia."""
    for a in azules:
        d = abs((h["theta"] - a["theta"] + 180) % 360 - 180)
        if d <= (h["ancho"] + a["ancho"]) / 2 + (C.W_H0 or 15.0):
            return True
    return False


def huecos_fuera_tolerancia(car):
    if C.W_H0 is None or C.W_H_TOL is None:
        return []
    return [h for h in car["huecos"]
            if abs(h["ancho"] - C.W_H0) > C.W_H_TOL and not _vecino_de_azul(h, car["azules"])]


def barras_fuera_tolerancia(car):
    if C.W_B0 is None or C.W_B_TOL is None:
        return []
    return [b for b in car["barras"]
            if abs(b["ancho"] - C.W_B0) > C.W_B_TOL and not _vecino_de_azul(b, car["azules"])]


def espacios_fuera_tolerancia(car):
    """Orificios y barras fuera de tolerancia, ordenados desde la marca, con etiqueta E1, E2…"""
    lista = ([{**h, "tipo": "orificio", "nominal": C.W_H0, "tol": C.W_H_TOL} for h in huecos_fuera_tolerancia(car)]
             + [{**b, "tipo": "barra", "nominal": C.W_B0, "tol": C.W_B_TOL} for b in barras_fuera_tolerancia(car)])
    lista.sort(key=lambda d: d["rel"] if d["rel"] is not None else d["theta"])
    for i, d in enumerate(lista, 1):
        d["etiqueta"] = f"E{i}"
    return lista


def clasificar(car, val):
    """Asigna las clases A y B, arma la lista de defectos y da el veredicto."""
    if not val["pasa"]:
        return {"veredicto": "NO DIAGNOSTICABLE", "clases_A": [], "clase_B": None,
                "defectos": [], "advertencias": [], "motivos": val["motivos"], "espacios": []}

    N, k, N0 = car["N"], car["k_star"], C.N0
    clases_A, defectos, adv = [], [], []

    if car["N_azul"] >= 1:
        clases_A.append("A1")
        for d in sorted(car["azules"], key=lambda a: int(a["etiqueta"][1:])):
            defectos.append({"clase": "A1", "etiqueta": d["etiqueta"], "theta": d["theta"],
                             "texto": f"Sector ausente {_donde(d)}."})
        if k != N0:
            adv.append(f"Hay un sector ausente pero el patrón se repite {k} veces en lugar de {N0}: "
                       "conviene revisar la imagen")

    espacios = []
    es_A3 = k > N0 or N > N0
    if es_A3:
        clases_A.append("A3")
        defectos.append({"clase": "A3", "etiqueta": "", "theta": None,
                         "texto": f"Sector añadido, {N} orificios detectados."})
    else:
        espacios = espacios_fuera_tolerancia(car)
        if k < N0 or espacios:
            clases_A.append("A2")
            if k < N0:
                defectos.append({"clase": "A2", "etiqueta": "", "theta": None,
                                 "texto": f"Ancho incorrecto: el patrón se repite {k} veces en lugar de {N0}."})
            for e in espacios:
                cual = "Orificio" if e["tipo"] == "orificio" else "Separación entre orificios"
                comp = "más ancha" if e["tipo"] == "barra" else "más ancho"
                if e["ancho"] < e["nominal"]:
                    comp = "más angosta" if e["tipo"] == "barra" else "más angosto"
                defectos.append({"clase": "A2", "etiqueta": e["etiqueta"], "theta": e["theta"],
                                 "texto": f"{cual} {comp} de lo normal {_donde(e)}: mide {e['ancho']:.0f}° "
                                          f"(normal {e['nominal']:.0f}° ± {e['tol']:.1f}°)."})

    if not clases_A:
        clases_A = ["A0"] if (N == N0 and k == N0) else ["A9"]
        if clases_A == ["A9"]:
            defectos.append({"clase": "A9", "etiqueta": "", "theta": None,
                             "texto": f"No se reconoce el patrón: se encontraron {N} orificios y el patrón "
                                      f"se repite {k} veces."})

    clase_B = "B1" if car["manchas"] else "B0"
    for m in car["manchas"]:
        defectos.append({"clase": "B1", "etiqueta": m["etiqueta"], "theta": m["theta"],
                         "texto": f"Mancha roja {_donde(m)}. Cubre el {m['area_pct']:.1f} % del disco."})

    veredicto = "CORRECTO" if clases_A == ["A0"] and clase_B == "B0" else "DEFECTUOSO"
    return {"veredicto": veredicto, "clases_A": clases_A, "clase_B": clase_B,
            "defectos": defectos, "advertencias": adv, "motivos": [], "espacios": espacios}
