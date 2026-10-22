"""
Medición por lotes y reglas de umbral (sección 9).

Usa los mismos módulos del sistema. Las salidas van a datos/salidas_calibracion/
y los umbrales a datos/calibracion.json. Pasos:

  python calibrar.py etiquetas --fotos "../Fotos T2"   # 1. etiquetas.csv
  python calibrar.py medir                              # 2. mediciones.csv (bloques 1 a 6, sin decidir)
  python calibrar.py color                              # 3. muestras_color.json (manual, cv2.selectROI)
  python calibrar.py umbrales                           # 4. calibracion.json
  python calibrar.py revisar                            # 5. resultados.csv + gráficas para el anexo
  python calibrar.py todo --fotos "../Fotos T2"         #    1 + 2 + 4 + 5
  python calibrar.py ruido --zip ruido_diseno_….zip     # barrido de K_BILATERAL y σ vs σ̂

Reglas (nunca se ajusta un valor a mano; si una regla no separa, se
corrige la regla y se recalibra):
  - Separar dos grupos: punto medio entre los extremos de cada grupo.
  - σ_cámara: percentil 95 de σ̂ en fotos limpias + margen.
  - Tolerancias: 3σ del disco correcto.
  - Niveles: terciles del grupo bueno.
"""
import argparse
import datetime as dt
import json
import os
from multiprocessing import Pool

import numpy as np
import pandas as pd

from subfunciones import config as C
from subfunciones.adquisicion import EXTENSIONES as EXT

RUTA_ETIQ = os.path.join(C.DIR_SALIDAS, "etiquetas.csv")
RUTA_MED = os.path.join(C.DIR_SALIDAS, "mediciones.csv")
RUTA_COLOR = os.path.join(C.DIR_SALIDAS, "muestras_color.json")
RUTA_RES = os.path.join(C.DIR_SALIDAS, "resultados.csv")
RUTA_BARRIDO = os.path.join(C.DIR_SALIDAS, "ruido_barrido.csv")
DIR_GRAF = os.path.join(C.DIR_SALIDAS, "graficas")

# Qué condición de captura debe fallar y por qué criterio (diseño "un factor a la vez").
# Las fotos de inclinación actuales (~40°) se conservan como "inclinación excesiva".
MALAS = {
    "Desenfocadas": "enfoque",
    "Mucho brillo": "exposicion",
    "Inclinación": "inclinacion",
}
MARGEN_SIGMA = 0.5


# ------------------------------------------------------------------ 1. etiquetas

def condicion_de(ruta_rel):
    partes = ruta_rel.replace("\\", "/").split("/")[:-1]
    return "/".join(partes) if partes else "sin_condicion"


def mala_por(condicion):
    for clave, criterio in MALAS.items():
        if clave.lower() in condicion.lower():
            return criterio
    return ""


def cmd_etiquetas(fotos, sugerir=True):
    """Crea etiquetas.csv: condición, conjunto y criterio que debería fallar por foto."""
    fotos = os.path.abspath(fotos)
    filas = []
    for raiz, _, archivos in os.walk(fotos):
        for a in sorted(archivos):
            if a.lower().endswith(EXT):
                rel = os.path.relpath(os.path.join(raiz, a), fotos)
                filas.append({"archivo": rel, "condicion": condicion_de(rel)})
    df = pd.DataFrame(filas).sort_values("archivo").reset_index(drop=True)
    # tríos de exposición: el 3.er disparo de cada trío va a prueba, el resto a diseño
    df["conjunto"] = df.groupby("condicion").cumcount().map(lambda i: "prueba" if i % 3 == 2 else "diseno")
    df["debe_fallar"] = df["condicion"].map(mala_por)
    df["disco"] = ""
    df["disco_origen"] = ""
    os.makedirs(C.DIR_SALIDAS, exist_ok=True)
    df.to_csv(RUTA_ETIQ, index=False)
    with open(RUTA_ETIQ + ".raiz", "w", encoding="utf-8") as f:
        f.write(fotos)
    print(f"etiquetas.csv: {len(df)} fotos en {df['condicion'].nunique()} condiciones")
    if sugerir:
        print("Sugiriendo el tipo de disco a partir de k* y N_azul (revísalo en etiquetas.csv)…")
        med = cmd_medir()
        _sugerir_disco(med)


def _sugerir_disco(med):
    """Llena la columna disco con una sugerencia a partir de k* y N_azul."""
    et = pd.read_csv(RUTA_ETIQ, keep_default_na=False)
    m = med.set_index("archivo")

    def sugerencia(a):
        if a not in m.index or not m.loc[a, "seg_ok"]:
            return ""
        r = m.loc[a]
        if r["N_azul"] >= 1:
            return "ausente"
        return {11: "anchura", 16: "anadido", 12: "correcto"}.get(int(r["k_star"]), "")

    vacios = et["disco"] == ""
    et.loc[vacios, "disco"] = et.loc[vacios, "archivo"].map(sugerencia)
    et.loc[vacios & (et["disco"] != ""), "disco_origen"] = "sugerido"
    et.to_csv(RUTA_ETIQ, index=False)
    print(et["disco"].value_counts().to_string())


def _raiz():
    """Carpeta de fotos usada al crear etiquetas.csv (por defecto ../Fotos T2)."""
    if os.path.exists(RUTA_ETIQ + ".raiz"):
        with open(RUTA_ETIQ + ".raiz", encoding="utf-8") as f:
            r = f.read().strip()
        if os.path.isdir(r):
            return r
    return C.DIR_FOTOS


# ------------------------------------------------------------------ 2. medir

def _medir_uno(args):
    raiz, archivo = args
    from subfunciones import pipeline
    try:
        fila = pipeline.medir(os.path.join(raiz, archivo))
    except Exception as e:  # una foto rota no detiene el lote
        fila = {"seg_ok": False, "error": str(e)}
    fila["archivo"] = archivo
    return fila


def _lote(func, archivos):
    """Aplica func a cada foto en paralelo y muestra el avance."""
    raiz = _raiz()
    n = max(1, (os.cpu_count() or 2) - 1)
    with Pool(n) as p:
        filas = []
        for i, f in enumerate(p.imap(func, [(raiz, a) for a in archivos]), 1):
            filas.append(f)
            print(f"\r  {i}/{len(archivos)}", end="", flush=True)
    print()
    return filas


def cmd_medir():
    """Crea mediciones.csv con las métricas de cada foto."""
    et = pd.read_csv(RUTA_ETIQ, keep_default_na=False)
    print(f"Midiendo {len(et)} fotos (bloques 1 a 6, sin decidir)…")
    med = pd.DataFrame(_lote(_medir_uno, list(et["archivo"])))
    med = et.merge(med, on="archivo")
    med.to_csv(RUTA_MED, index=False)
    print(f"mediciones.csv: {len(med)} filas")
    return med


# ------------------------------------------------------------------ 3. color

CLASES_COLOR = ["material", "marca", "bloque_azul", "mancha", "fondo"]


def cmd_color(n_por_clase=3):
    """Muestras de color a mano con cv2.selectROI (única parte manual)."""
    import cv2
    from subfunciones import adquisicion
    et = pd.read_csv(RUTA_ETIQ, keep_default_na=False)
    et = et[et["conjunto"] == "diseno"]
    raiz = _raiz()
    muestras = {c: [] for c in CLASES_COLOR}
    for clase in CLASES_COLOR:
        candidatas = et.sample(min(n_por_clase, len(et)), random_state=len(clase))
        for a in candidatas["archivo"]:
            img = adquisicion.reducir(adquisicion.leer(os.path.join(raiz, a)), 1400)[0]
            titulo = f"{clase}: arrastra un rectángulo, ENTER acepta, C omite"
            x, y, w, h = cv2.selectROI(titulo, img, showCrosshair=True)
            cv2.destroyWindow(titulo)
            if w * h == 0:
                continue
            hsv = cv2.cvtColor(img[y:y + h, x:x + w], cv2.COLOR_BGR2HSV).reshape(-1, 3)
            muestras[clase].append({"archivo": a, "H": hsv[:, 0].tolist(), "S": hsv[:, 1].tolist(),
                                    "V": hsv[:, 2].tolist()})
    with open(RUTA_COLOR, "w", encoding="utf-8") as f:
        json.dump(muestras, f)
    _histogramas_color(muestras)
    print(f"muestras_color.json guardado ({sum(len(v) for v in muestras.values())} recortes)")


def _histogramas_color(muestras):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    os.makedirs(DIR_GRAF, exist_ok=True)
    fig, ax = plt.subplots(1, 3, figsize=(13, 3.4))
    for clase, lista in muestras.items():
        if not lista:
            continue
        for i, canal in enumerate("HSV"):
            datos = np.concatenate([m[canal] for m in lista])
            ax[i].hist(datos, bins=64, range=(0, 180 if canal == "H" else 256), histtype="step",
                       density=True, label=clase)
    for i, canal in enumerate("HSV"):
        ax[i].set_title(canal)
    ax[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(DIR_GRAF, "histogramas_hsv.png"), dpi=130)
    plt.close(fig)


# ------------------------------------------------------------------ 4. umbrales

def _separar(buenos, malos, mayor_es_bueno=True):
    """Umbral entre dos grupos. Devuelve (umbral, separa).

    Si los grupos no se traslapan: punto medio entre sus extremos.
    Si se traslapan: el umbral con menos errores; entre empates, el centro
    del hueco más ancho entre valores consecutivos (máximo margen).
    """
    b, m = np.asarray(buenos, float), np.asarray(malos, float)
    if len(b) == 0 or len(m) == 0:
        return None, False
    if not mayor_es_bueno:
        b, m = -b, -m
    if b.min() > m.max():
        u = (b.min() + m.max()) / 2
        return float(u if mayor_es_bueno else -u), True
    v = np.unique(np.concatenate([b, m]))
    candidatos = (v[:-1] + v[1:]) / 2
    huecos = v[1:] - v[:-1]
    errores = np.array([(b < t).sum() + (m >= t).sum() for t in candidatos])
    mejores = np.flatnonzero(errores == errores.min())
    u = candidatos[mejores[np.argmax(huecos[mejores])]]
    return float(u if mayor_es_bueno else -u), False


def _r(x, n=3):
    return None if x is None else round(float(x), n)


def cmd_umbrales():
    """Aplica las reglas a mediciones.csv y escribe calibracion.json."""
    med = pd.read_csv(RUTA_MED, keep_default_na=False)
    med = med[med["seg_ok"].astype(str) == "True"]
    d = med[med["conjunto"] == "diseno"]
    limpias = d[d["debe_fallar"] == ""]
    v, reglas = {}, {}

    def num(serie):
        return pd.to_numeric(serie, errors="coerce").dropna()

    # --- enfoque
    malos = num(d.loc[d["debe_fallar"] == "enfoque", "F"])
    buenos = num(d.loc[d["debe_fallar"] != "enfoque", "F"])
    u, sep = _separar(buenos, malos)
    if u is not None:
        v["F_MIN"] = _r(u)
        v["F_BUENO"] = _r(np.percentile(buenos, 33.3))
        reglas["F_MIN"] = (f"punto medio entre max(F desenfocadas)={malos.max():.3f} y min(F resto)="
                           f"{buenos.min():.3f}; separa={sep}. F_BUENO = tercil inferior del resto")

    # --- marca legible (las desenfocadas se excluyen: ya las rechaza el enfoque)
    malos = num(d.loc[d["debe_fallar"] == "exposicion", "z_marca"])
    buenos = num(d.loc[d["debe_fallar"].isin(["", "inclinacion"]), "z_marca"])
    u, sep = _separar(buenos, malos)
    if u is not None:
        v["Z_MIN"] = _r(u, 2)
        reglas["Z_MIN"] = (f"max(z mucho brillo)={malos.max():.2f}, min(z legibles)={buenos.min():.2f}; "
                           f"separa={sep}" + ("" if sep else "; umbral de mínimo error y máximo margen"))

    # --- exposición en la banda de la marca
    malos = num(d.loc[d["debe_fallar"] == "exposicion", "sat_marca"])
    buenos = num(d.loc[d["debe_fallar"] != "exposicion", "sat_marca"])
    u, sep = _separar(buenos, malos, mayor_es_bueno=False)
    if u is not None:
        v["SAT_MARCA_MAX"] = _r(u, 2)
        reglas["SAT_MARCA_MAX"] = (f"buenos hasta {buenos.max():.1f} %, mucho brillo desde {malos.min():.1f} %; "
                                   f"separa={sep}" + ("" if sep else
                                   "; umbral de mínimo error. Hay tomas con la banda recortada y la marca "
                                   "aún visible: el rechazo lo completa Z_MIN"))

    # --- contraste
    eta = num(limpias["eta"])
    if len(eta):
        v["ETA_MIN"] = _r(min(C.ETA_MIN, eta.min() - 0.02), 2)
        v["ETA_ALTO"] = _r(np.percentile(eta, 33.3), 2)
        reglas["ETA_MIN"] = (f"sin grupo malo en la sesión: se conserva {C.ETA_MIN} salvo que una foto limpia "
                             f"quede debajo (min η limpias = {eta.min():.2f}). ETA_ALTO = tercil")

    # --- ruido
    sig = num(limpias["sigma"])
    if len(sig):
        v["SIGMA_CAMARA"] = _r(np.percentile(sig, 95) + MARGEN_SIGMA, 2)
        reglas["SIGMA_CAMARA"] = f"p95(σ̂ limpias)={np.percentile(sig, 95):.2f} + {MARGEN_SIGMA}"

    # --- manchas (áreas en 3 órdenes de magnitud → punto medio en escala log)
    con = d["condicion"].str.contains("ancha", case=False)
    falsos = num(d.loc[~con & (d["debe_fallar"] == ""), "area_roja_max"])
    reales = num(d.loc[con & (d["debe_fallar"] == ""), "area_roja_max"])
    if len(falsos) and len(reales):
        fmax = max(falsos.max(), 1e-3)
        v["A_MIN"] = _r(np.sqrt(fmax * reales.min()), 3)
        reglas["A_MIN"] = (f"media geométrica entre la mayor falsa detección sin manchas ({fmax:.3f} %) y la "
                           f"menor mancha principal en fotos manchadas ({reales.min():.2f} %)")

    # --- tolerancia de ancho de hueco (disco correcto, fotos que pasan calidad)
    correctos = limpias[(limpias["disco"] == "correcto") & (pd.to_numeric(limpias["N"], errors="coerce") == C.N0)]
    anchos = np.concatenate([np.array(str(s).split(";"), float) for s in correctos["w_h"] if str(s)]) \
        if len(correctos) else np.array([])
    if len(anchos) > 10:
        v["W_H0"] = _r(anchos.mean(), 2)
        v["W_H_TOL"] = _r(max(3 * anchos.std(), 1.0), 2)
        reglas["W_H_TOL"] = (f"media ± 3σ de {len(anchos)} huecos del disco correcto "
                             f"({len(correctos)} fotos); piso 1° (resolución ±0,5°)")

    barras = np.concatenate([np.array(str(s).split(";"), float) for s in correctos["w_b"] if str(s)]) \
        if len(correctos) else np.array([])
    if len(barras) > 10:
        v["W_B0"] = _r(barras.mean(), 2)
        v["W_B_TOL"] = _r(max(3 * barras.std(), 1.0), 2)
        reglas["W_B_TOL"] = (f"media ± 3σ de {len(barras)} barras entre orificios del disco correcto "
                             f"({len(correctos)} fotos); piso 1°")

    # --- color (si se tomaron muestras)
    if os.path.exists(RUTA_COLOR):
        with open(RUTA_COLOR, encoding="utf-8") as f:
            mu = json.load(f)

        def canal(clase, c):
            lista = mu.get(clase, [])
            return np.concatenate([m[c] for m in lista]) if lista else np.array([])

        s_mat = canal("material", "S")
        s_mancha, s_azul = canal("mancha", "S"), canal("bloque_azul", "S")
        if len(s_mat) and len(s_mancha):
            v["S_ROJO"] = _r((np.percentile(s_mat, 99) + np.percentile(s_mancha, 5)) / 2, 0)
            reglas["S_ROJO"] = "punto medio entre p99(S material) y p5(S mancha)"
        if len(s_mat) and len(s_azul):
            v["S_MIN"] = _r((np.percentile(s_mat, 99) + np.percentile(s_azul, 5)) / 2, 0)
            reglas["S_MIN"] = "punto medio entre p99(S material) y p5(S bloque azul)"

    # se conservan los valores que este paso no recalcula (p. ej. K_BILATERAL del barrido de ruido)
    if os.path.exists(C.RUTA_CALIBRACION):
        with open(C.RUTA_CALIBRACION, encoding="utf-8") as f:
            previo = json.load(f)
        for k, val in previo.get("valores", {}).items():
            if k not in v:
                v[k] = val
                if k in previo.get("reglas", {}):
                    reglas[k] = previo["reglas"][k]

    salida = {"version": "v0", "fecha": dt.datetime.now().isoformat(timespec="seconds"),
              "fotos_diseno": int(len(d)), "valores": v, "reglas": reglas,
              "sin_calibrar": {k: t for k, t in {
                  "THETA_MAX": "faltan fotos a 15–20° (se conserva 30°)",
                  "K_BILATERAL": "requiere el barrido con el generador de ruido",
                  "SIGMA_ALTO": "requiere imágenes con ruido sintético"}.items() if k not in v}}
    with open(C.RUTA_CALIBRACION, "w", encoding="utf-8") as f:
        json.dump(salida, f, indent=2, ensure_ascii=False)
    print("calibracion.json:")
    for k, val in v.items():
        print(f"  {k:15s} = {val}")
        if k in reglas:
            print(f"      {reglas[k]}")


# ------------------------------------------------------------------ 5. revisar

def _analizar_uno(args):
    raiz, archivo = args
    from subfunciones import pipeline
    C.cargar_calibracion()          # el proceso hijo debe ver la calibración recién escrita
    try:
        r = pipeline.analizar(os.path.join(raiz, archivo))
    except Exception as e:
        return {"archivo": archivo, "veredicto": "ERROR", "motivos": str(e)}
    cls, val = r["cls"], r["val"]
    fila = {"archivo": archivo, "veredicto": cls["veredicto"],
            "clases_A": "+".join(cls["clases_A"]), "clase_B": cls["clase_B"] or "",
            "motivos": " | ".join(val["motivos"]),
            "criterios_fallados": ";".join(c["nombre"] for c in val["criterios"] if not c["ok"])}
    if "car" in r:
        c = r["car"]
        fila.update({"N": c["N"], "k_star": c["k_star"], "N_azul": c["N_azul"],
                     "n_manchas": len(c["manchas"]), "theta_ref": c["theta_ref"]})
    return fila


ESPERADO_A = {"correcto": "A0", "ausente": "A1", "anchura": "A2", "anadido": "A3"}


def cmd_revisar():
    """Corre el sistema completo sobre todas las fotos y compara con lo esperado."""
    import importlib
    importlib.reload(C)
    et = pd.read_csv(RUTA_ETIQ, keep_default_na=False)
    print(f"Revisando {len(et)} fotos con el sistema completo…")
    res = pd.DataFrame(_lote(_analizar_uno, list(et["archivo"])))
    res = et.merge(res, on="archivo")
    con_manchas = res["condicion"].str.contains("ancha", case=False)
    res["A_esperado"] = res["disco"].map(ESPERADO_A).fillna("")
    res["B_esperado"] = np.where(con_manchas, "B1", "B0")
    diag = res["veredicto"].isin(["CORRECTO", "DEFECTUOSO"])
    res["acierto_A"] = np.where(diag, res["clases_A"] == res["A_esperado"], np.nan)
    res["acierto_B"] = np.where(diag, res["clase_B"] == res["B_esperado"], np.nan)
    res["rechazo_esperado"] = res["debe_fallar"] != ""
    res["rechazo_correcto"] = (~diag) == res["rechazo_esperado"]
    res.to_csv(RUTA_RES, index=False)

    resumen = res.groupby(["condicion"]).agg(
        fotos=("archivo", "size"),
        diagnosticables=("veredicto", lambda s: int(s.isin(["CORRECTO", "DEFECTUOSO"]).sum())),
        decision_validacion_ok=("rechazo_correcto", "sum"),
        acierto_A=("acierto_A", "mean"), acierto_B=("acierto_B", "mean"))
    pd.set_option("display.width", 200)
    print(resumen.round(2).to_string())
    for conj in ["diseno", "prueba"]:
        s = res[res["conjunto"] == conj]
        print(f"[{conj}] validación correcta: {s['rechazo_correcto'].mean():.0%} · "
              f"eje A: {pd.to_numeric(s['acierto_A']).mean():.0%} · eje B: {pd.to_numeric(s['acierto_B']).mean():.0%}")
    _graficas()
    print(f"resultados.csv y gráficas en {DIR_GRAF}")


def _graficas():
    """Distribución de cada métrica por condición con su umbral (anexo)."""
    import importlib
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    importlib.reload(C)
    med = pd.read_csv(RUTA_MED, keep_default_na=False)
    med = med[med["seg_ok"].astype(str) == "True"]
    os.makedirs(DIR_GRAF, exist_ok=True)
    conds = sorted(med["condicion"].unique())
    for col, umbral, titulo in [("F", C.F_MIN, "Enfoque F"), ("z_marca", C.Z_MIN, "Puntaje de la marca z"),
                                ("sat_marca", C.SAT_MARCA_MAX, "% recortado en la banda de la marca"),
                                ("eta", C.ETA_MIN, "Separabilidad η"), ("sigma", C.SIGMA_CAMARA, "σ̂ (Immerkaer)"),
                                ("inclinacion", C.THETA_MAX, "Inclinación (°)")]:
        fig, ax = plt.subplots(figsize=(9, 0.42 * len(conds) + 1.2))
        for i, cnd in enumerate(conds):
            x = pd.to_numeric(med.loc[med["condicion"] == cnd, col], errors="coerce")
            ax.scatter(x, np.full(len(x), i) + np.random.uniform(-0.15, 0.15, len(x)), s=16,
                       color="#d23b3b" if mala_por(cnd) else "#1d2430", alpha=0.8)
        ax.axvline(umbral, color="#3446d4", lw=1.5)
        ax.set_yticks(range(len(conds)))
        ax.set_yticklabels(conds, fontsize=8)
        ax.set_title(f"{titulo} — umbral {umbral}", fontsize=10)
        for lado in ("top", "right"):
            ax.spines[lado].set_visible(False)
        fig.tight_layout()
        fig.savefig(os.path.join(DIR_GRAF, f"{col}.png"), dpi=130)
        plt.close(fig)

    # marca: contraste relativo vs Canny (6.3)
    th, tc = pd.to_numeric(med["theta_marca"], errors="coerce"), pd.to_numeric(med["theta_canny"], errors="coerce")
    med = med.assign(concuerda=((th - tc + 180) % 360 - 180).abs() <= 3)
    tabla = med.groupby("condicion")["concuerda"].agg(["sum", "size"])
    tabla.to_csv(os.path.join(DIR_GRAF, "marca_contraste_vs_canny.csv"))
    print("Canny vs contraste relativo (±3°):")
    print(tabla.to_string())


# ------------------------------------------------------------------ ruido (barrido)

K_BARRIDO = [1.0, 2.0, 3.0, 4.0, 6.0]


def _firma(r):
    if "car" not in r:
        return ("NO DIAGNOSTICABLE",)
    c = r["car"]
    return (r["cls"]["veredicto"], c["N"], c["k_star"], c["N_azul"], len(c["manchas"]))


def _ruido_uno(args):
    ruta, origen, K = args
    from subfunciones import pipeline
    C.cargar_calibracion()
    C.K_BILATERAL = K
    r = pipeline.analizar(ruta)
    return {"sigma_hat": r["rui"]["sigma"] if "rui" in r else np.nan, "filtro": r.get("rui", {}).get("filtro", ""),
            "firma": "|".join(map(str, _firma(r)))}


def cmd_ruido(ruta_zip):
    """Barrido de K_BILATERAL sobre un lote del generador y relación σ generada vs σ̂."""
    import tempfile
    import zipfile
    from subfunciones import pipeline
    d = tempfile.mkdtemp(prefix="barrido_")
    with zipfile.ZipFile(ruta_zip) as z:
        z.extractall(d)
    csvs = [f for f in os.listdir(d) if f.endswith(".csv")]
    lote = pd.read_csv(os.path.join(d, csvs[0]))
    et = pd.read_csv(RUTA_ETIQ, keep_default_na=False)
    por_nombre = {os.path.basename(a): a for a in et["archivo"]}
    raiz = _raiz()
    # firma de referencia: la foto limpia de origen
    ref = {}
    for o in lote["origen"].unique():
        if o in por_nombre:
            ref[o] = "|".join(map(str, _firma(pipeline.analizar(os.path.join(raiz, por_nombre[o])))))
    tareas = [(os.path.join(d, f["archivo"]), f["origen"], K) for K in K_BARRIDO for _, f in lote.iterrows()]
    n = max(1, (os.cpu_count() or 2) - 1)
    with Pool(n) as p:
        filas = p.map(_ruido_uno, tareas)
    res = pd.DataFrame([{**dict(zip(["ruta", "origen", "K"], t)), **f} for t, f in zip(tareas, filas)])
    res = res.merge(lote.assign(ruta=lote["archivo"].map(lambda a: os.path.join(d, a)))[["ruta", "sigma"]], on="ruta")
    res["igual_a_limpia"] = res.apply(lambda r: ref.get(r["origen"]) == r["firma"], axis=1)
    res.drop(columns=["ruta"]).to_csv(RUTA_BARRIDO, index=False)
    tabla = res.groupby("K")["igual_a_limpia"].mean()
    print("Fracción con el mismo diagnóstico que la foto limpia:")
    print(tabla.round(3).to_string())
    k1 = res[res["K"] == K_BARRIDO[0]]
    pend = float(np.polyfit(k1["sigma"], k1["sigma_hat"], 1)[0])
    print(f"σ̂ ≈ {pend:.3f}·σ generada (ajuste lineal, {len(k1)} imágenes)")
    empatados = [float(k) for k in tabla.index[tabla.values == tabla.max()]]
    with open(C.RUTA_CALIBRACION, encoding="utf-8") as f:
        cal = json.load(f)
    previo = cal.get("valores", {}).get("K_BILATERAL", 2.0)
    # empate: se conserva el valor vigente si está entre los mejores; si no, el K más pequeño
    mejor = float(previo) if float(previo) in empatados else empatados[0]
    cal["valores"]["K_BILATERAL"] = mejor
    cal.setdefault("reglas", {})["K_BILATERAL"] = (f"barrido {K_BARRIDO} sobre {os.path.basename(ruta_zip)}; "
                                                   f"K con la mayor coincidencia ({tabla.max():.0%}); en empate se conserva el vigente. "
                                                   f"σ̂ ≈ {pend:.3f}·σ")
    cal.get("sin_calibrar", {}).pop("K_BILATERAL", None)
    with open(C.RUTA_CALIBRACION, "w", encoding="utf-8") as f:
        json.dump(cal, f, indent=2, ensure_ascii=False)
    print(f"K_BILATERAL = {mejor} guardado en calibracion.json")


# ------------------------------------------------------------------ CLI

def main():
    ap = argparse.ArgumentParser(description="Calibración del diagnóstico de codificador (v1.4)")
    ap.add_argument("paso", choices=["etiquetas", "medir", "color", "umbrales", "revisar", "ruido", "todo"])
    ap.add_argument("--fotos", default=C.DIR_FOTOS,
                    help="carpeta con las fotos (subcarpetas = condiciones)")
    ap.add_argument("--zip", help="ZIP del generador de ruido (paso 'ruido')")
    ap.add_argument("--sin-sugerir", action="store_true", help="no sugerir el tipo de disco")
    a = ap.parse_args()

    if a.paso == "etiquetas":
        cmd_etiquetas(a.fotos, not a.sin_sugerir)
    elif a.paso == "medir":
        cmd_medir()
    elif a.paso == "color":
        cmd_color()
    elif a.paso == "umbrales":
        cmd_umbrales()
    elif a.paso == "revisar":
        cmd_revisar()
    elif a.paso == "ruido":
        if not a.zip:
            ap.error("el paso 'ruido' necesita --zip con un lote del generador")
        cmd_ruido(a.zip)
    elif a.paso == "todo":
        if not os.path.exists(RUTA_ETIQ):
            cmd_etiquetas(a.fotos, True)
        else:
            cmd_medir()
        cmd_umbrales()
        cmd_revisar()


if __name__ == "__main__":
    main()
