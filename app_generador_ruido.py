"""
Generador de ruido (aplicación aparte, sección 5).

    python app_generador_ruido.py  → http://127.0.0.1:7861

I_r = clip(I0 + n), n ~ N(0, σ²) por píxel y canal, sobre la resolución
original. σ uniforme aleatoria por variante: diseño [5, 20], prueba [20, 40].
Salida: ZIP con JPG (calidad 95) + CSV (archivo, origen, conjunto, σ, semilla).
El sistema de diagnóstico nunca lee este CSV.
"""
import csv
import io
import os
import tempfile
import time
import zipfile

import cv2
import gradio as gr
import numpy as np

from subfunciones import adquisicion
from subfunciones import config as C
from subfunciones.estilo_interfaz import CSS, GR_MAYOR

RANGOS = {"diseño": C.SIGMA_DISENO, "prueba": C.SIGMA_PRUEBA}
SUFIJO = {"diseño": "diseno", "prueba": "prueba"}


def agregar_ruido(I0, sigma, semilla):
    """I_r = clip(I0 + n), con n ~ N(0, σ²) por píxel y canal."""
    rng = np.random.default_rng(semilla)
    n = rng.normal(0.0, sigma, I0.shape)
    return np.clip(I0.astype(np.float64) + n, 0, 255).astype(np.uint8)


def generar_lote(rutas, conjunto, semilla_base, variantes=None, progreso=None):
    """Devuelve (ruta_zip, filas_csv, miniaturas[(img_rgb, texto)])."""
    variantes = variantes or C.VARIANTES
    lo, hi = RANGOS[conjunto]
    rng_sigma = np.random.default_rng(semilla_base)
    salida = tempfile.mkdtemp(prefix="ruido_")
    nombre_zip = os.path.join(salida, f"ruido_{SUFIJO[conjunto]}_{time.strftime('%Y%m%d_%H%M%S')}.zip")
    filas, miniaturas = [], []
    total = len(rutas) * variantes
    hechos = 0
    with zipfile.ZipFile(nombre_zip, "w", zipfile.ZIP_STORED) as z:
        for ruta in rutas:
            I0 = adquisicion.leer(ruta)
            base = os.path.splitext(os.path.basename(ruta))[0]
            for v in range(1, variantes + 1):
                sigma = float(rng_sigma.uniform(lo, hi))
                semilla = int(semilla_base * 1000 + hechos)
                Ir = agregar_ruido(I0, sigma, semilla)
                nombre = f"{base}_ruido_{SUFIJO[conjunto]}_s{sigma:.1f}_v{v}.jpg"
                ok, buf = cv2.imencode(".jpg", Ir, [cv2.IMWRITE_JPEG_QUALITY, C.CALIDAD_JPG])
                z.writestr(nombre, buf.tobytes())
                filas.append({"archivo": nombre, "origen": os.path.basename(ruta), "conjunto": SUFIJO[conjunto],
                              "sigma": round(sigma, 2), "semilla": semilla})
                # miniatura: recorte central a escala 1:1 para que el grano sea visible
                h, w = Ir.shape[:2]
                c = 160
                rec = Ir[h // 2 - c:h // 2 + c, w // 2 - c:w // 2 + c]
                miniaturas.append((cv2.cvtColor(rec, cv2.COLOR_BGR2RGB), f"{base}  v{v}  σ = {sigma:.1f}"))
                hechos += 1
                if progreso:
                    progreso(hechos / total, desc=f"{hechos}/{total}")
        texto = io.StringIO()
        w = csv.DictWriter(texto, fieldnames=["archivo", "origen", "conjunto", "sigma", "semilla"])
        w.writeheader()
        w.writerows(filas)
        z.writestr(f"ruido_{SUFIJO[conjunto]}.csv", texto.getvalue())
    return nombre_zip, filas, miniaturas


def construir():
    """Arma la interfaz del generador."""
    tema = gr.themes.Base(neutral_hue="slate", font=[gr.themes.GoogleFont("Archivo"), "system-ui", "sans-serif"],
                          primary_hue="indigo")
    kw = {"theme": tema, "css": CSS}
    with gr.Blocks(title="Generador de ruido", **(kw if GR_MAYOR < 6 else {})) as app:
        gr.HTML('<div id="ed-cabecera"><h1>Generador de ruido gaussiano</h1>'
                '<p>Crea variantes ruidosas de fotos limpias para probar el bloque de ruido. '
                'El ruido se aplica a la resolución original, por píxel y por canal.</p></div>')
        with gr.Row(equal_height=False):
            with gr.Column(scale=4, min_width=300):
                fotos = gr.File(label="Fotos limpias (5–10, JPG o PNG)", file_count="multiple",
                                file_types=list(adquisicion.EXTENSIONES), type="filepath")
                conjunto = gr.Radio(list(RANGOS), value="diseño", label="Conjunto",
                                    info=f"diseño: σ en {list(C.SIGMA_DISENO)}   prueba: σ en {list(C.SIGMA_PRUEBA)}")
                semilla = gr.Number(value=2026, precision=0, label="Semilla base",
                                    info="La misma semilla reproduce exactamente el mismo lote.")
                boton = gr.Button("Generar", variant="primary", size="lg")
                descarga = gr.File(label="Descargar todo (ZIP con JPG + CSV)", interactive=False)
            with gr.Column(scale=8, min_width=420):
                galeria = gr.Gallery(label="Recorte central 1:1 de cada variante", columns=3, height=620,
                                     object_fit="cover")
                tabla = gr.Dataframe(headers=["archivo", "origen", "conjunto", "sigma", "semilla"],
                                     interactive=False, wrap=True)

        def correr(rutas, conj, sem, progress=gr.Progress()):
            if not rutas:
                raise gr.Error("Sube al menos una foto limpia.")
            rutas = rutas if isinstance(rutas, list) else [rutas]
            rutas = [r if isinstance(r, str) else r.name for r in rutas]
            z, filas, mini = generar_lote(rutas, conj, int(sem), progreso=progress)
            datos = [[f["archivo"], f["origen"], f["conjunto"], f["sigma"], f["semilla"]] for f in filas]
            return mini, datos, z

        boton.click(correr, [fotos, conjunto, semilla], [galeria, tabla, descarga])
    return app, kw


if __name__ == "__main__":
    app, kw = construir()
    lanzar = {"inbrowser": not os.environ.get("ED_SIN_NAVEGADOR"), "server_port": 7861}
    if GR_MAYOR >= 6:
        lanzar.update(kw)
    app.queue().launch(**lanzar)
