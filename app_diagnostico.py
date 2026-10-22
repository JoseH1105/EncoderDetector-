"""
App del sistema de diagnóstico (sección 7).

    python app_diagnostico.py      → http://127.0.0.1:7860

Carga una foto JPG o PNG, pulsa "Diagnosticar" y los resultados aparecen
etapa por etapa (función generadora). Si la validación falla, el
proceso se detiene en esa etapa y explica el motivo.
"""
import glob
import html
import math
import os

import gradio as gr

from subfunciones import adquisicion, pipeline
from subfunciones import config as C
from subfunciones import visualizacion as vz
from subfunciones.clasificacion import SENCILLO_A, SENCILLO_B
from subfunciones.estilo_interfaz import CSS, GR_MAYOR

FOTOS = C.DIR_FOTOS

ETAPAS = [("segmentacion", "Ubicar el disco"), ("ruido", "Limpiar ruido"), ("validacion", "Revisar la foto"),
          ("caracteristicas", "Medir el disco"), ("resultado", "Resultado")]
TAB_DE = {"segmentacion": "t4", "ruido": "t1", "validacion": "t2", "caracteristicas": "t3", "resultado": "t4"}

ESTADO_INICIAL = {k: "pendiente" for k, _ in ETAPAS}


def anillo(estado, centro="", sub="", girando=False, final=None):
    """Indicador de progreso con forma de disco codificador: un sector por etapa.
    Al terminar, los sectores completados toman el color del veredicto."""
    color = {"pendiente": "var(--ed-linea)", "activo": "var(--ed-azul)",
             "hecho": "var(--ed-tinta)", "fallo": "var(--ed-rojo)", "omitido": "var(--ed-suave)"}
    if final:
        color["hecho"] = {"CORRECTO": "var(--ed-verde)", "DEFECTUOSO": "var(--ed-rojo)"}.get(final, "#5b6372")
    cx = cy = 84
    r0, r1 = 52, 78
    sectores = []
    for i, (k, _) in enumerate(ETAPAS):
        a0 = math.radians(-90 + i * 72 + 4)
        a1 = math.radians(-90 + (i + 1) * 72 - 4)
        p = [(cx + r1 * math.cos(a0), cy + r1 * math.sin(a0)), (cx + r1 * math.cos(a1), cy + r1 * math.sin(a1)),
             (cx + r0 * math.cos(a1), cy + r0 * math.sin(a1)), (cx + r0 * math.cos(a0), cy + r0 * math.sin(a0))]
        d = (f"M{p[0][0]:.1f},{p[0][1]:.1f} A{r1},{r1} 0 0 1 {p[1][0]:.1f},{p[1][1]:.1f} "
             f"L{p[2][0]:.1f},{p[2][1]:.1f} A{r0},{r0} 0 0 0 {p[3][0]:.1f},{p[3][1]:.1f} Z")
        sectores.append(f'<path d="{d}" fill="{color[estado[k]]}"/>')
    giro = ('<circle class="ed-giro" cx="84" cy="84" r="45" fill="none" stroke="var(--ed-azul)" '
            'stroke-width="2" stroke-dasharray="18 265"/>') if girando else ""
    svg = (f'<svg viewBox="0 0 168 168" width="168" height="168" role="img" aria-label="Progreso del diagnóstico">'
           f'{"".join(sectores)}{giro}'
           f'<text x="84" y="86" text-anchor="middle" font-size="12.5" font-weight="700" fill="var(--ed-tinta)">'
           f'{html.escape(centro)}</text><text x="84" y="102" text-anchor="middle" font-size="9.5" '
           f'fill="var(--ed-gris)">{html.escape(sub)}</text></svg>')
    items = "".join(f'<li class="{estado[k]}"><span class="p"></span>{n}</li>' for k, n in ETAPAS)
    return f'<div class="ed-anillo">{svg}<ul class="ed-pasos">{items}</ul></div>'


def datos(pares):
    return '<div class="ed-datos">' + "".join(
        f'<div class="ed-dato"><b>{v}</b><span>{k}</span></div>' for k, v in pares) + "</div>"


def vacio(txt):
    return f'<div class="ed-vacio">{txt}</div>'


# ------------------------------------------------------------------ paneles

def datos_ubicacion(g):
    """Datos del disco, en una fila secundaria bajo el veredicto.

    El tamaño que se reporta es el aparente: píxeles del diámetro en la foto y su
    equivalente en mm según la foto de referencia (ver escala.py).
    """
    if not g["ok"]:
        pares = [("redondez del mejor contorno", f"{g['C']:.2f}"), ("contraste disco y fondo", f"{g['eta']:.2f}")]
        return '<p class="ed-sub">Datos del disco</p>' + datos(pares).replace('ed-datos', 'ed-datos ed-chico')
    ap = g.get("aparente") or {}
    mm = ap.get("mm")
    pares = [("diámetro en la foto", f"{g['D0']:.0f} px"),
             ("diámetro aparente", f"{mm:.1f} mm" if mm else "sin referencia"),
             ("escala de referencia", f"{ap['px_por_mm']:.1f} px por mm" if ap.get("px_por_mm") else "—"),
             ("inclinación", f"{g['inclinacion']:.1f}°"), ("redondez del contorno", f"{g['C']:.2f}"),
             ("centro en la foto (x, y)", f"{g['xc']:.0f}, {g['yc']:.0f}")]
    nota = ""
    if ap.get("reescalada"):
        nota = (f'<p class="ed-nota">La foto mide {ap["ancho"]}×{ap["alto"]} px; para compararla con la referencia '
                f'su diámetro se llevó a la resolución de la cámara ({ap["D_px_nativo"]:.0f} px).</p>')
    return ('<p class="ed-sub">Datos del disco</p>' + datos(pares).replace('ed-datos', 'ed-datos ed-chico') + nota)


LEYENDA = ('<div class="ed-leyenda"><span><i style="background:var(--ed-verde)"></i>borde del disco</span>'
           '<span><i style="background:#ffffff;border:1px solid var(--ed-gris)"></i>anillos de la corona</span>'
           '<span><i style="background:color-mix(in srgb, var(--ed-azul) 35%, transparent)"></i>'
           'franja donde se cuentan los orificios</span></div>')


def panel_segmentacion(r):
    """Primera vista del Resultado: el disco ubicado mientras sigue el análisis."""
    g = r["geo"]
    img = vz.segmentacion(r["adq"], g)
    if g["ok"]:
        cab = ('<div class="ed-veredicto ed-v-NO ed-espera"><h2>Disco ubicado</h2>'
               '<p>Analizando la foto…</p></div>')
    else:
        cab = ('<div class="ed-veredicto ed-v-NO"><h2>No se encontró el disco</h2>'
               f'<p>{html.escape(g.get("motivo", ""))}</p></div>')
    return img, cab + datos_ubicacion(g)


FILTROS = {"ninguno": "ninguno, no hace falta",
           "bilateral": "suavizado que conserva bordes",
           "gaussiano": "suavizado gaussiano"}


def panel_ruido(r):
    u = r["rui"]
    info = datos([("nivel de ruido", u["nivel"]), ("ruido medido", f"{u['sigma']:.2f}"),
                  ("filtro aplicado", FILTROS.get(u["filtro"], u["filtro"]))])
    return info, vz.antes_despues(r["nor"]["I_n"], u["I_f"])


def panel_validacion(r):
    v = r["val"]
    if v["pasa"]:
        cab = ('<div class="ed-veredicto ed-v-CORRECTO"><h2>La foto sirve</h2>'
               '<p>Cumple todas las condiciones para diagnosticar el disco.</p></div>')
    else:
        cab = ('<div class="ed-veredicto ed-v-NO"><h2>La foto no sirve para diagnosticar</h2><p>'
               + html.escape("; ".join(v["motivos"])) + ".</p></div>")
    return cab + vz.tabla_validacion(v)


def _angulo_ref(c):
    return f"{c['theta_ref']:.1f}°" if c["theta_ref"] is not None else "no encontrada"


def _puntos_linea(c):
    lin = c.get("linea")
    return f"{lin['n_usados']} de {len(lin['puntos'])}" if lin else "—"


def _separacion_linea(c, geo):
    """Separación entre la línea y el centro, en px de la foto original."""
    lin = c.get("linea")
    if not lin or lin["n_usados"] < 2:
        return "—"
    return f"{lin['separacion_px'] * geo['D0'] / C.DN:.1f} px"


def panel_caracteristicas(r):
    c = r["car"]
    ancho = sum(c["w_h"]) / max(len(c["w_h"]), 1)
    filas = [["Orificios encontrados", c["N"]],
             ["Veces que se repite el patrón en una vuelta", c["k_star"]],
             ["Sectores tapados de azul", c["N_azul"]],
             ["Manchas rojas", len(c["manchas"])],
             ["Ángulo de la línea de referencia (desde la horizontal)", _angulo_ref(c)],
             ["Visibilidad de la línea de referencia", f"{c['z_marca']:.1f}"],
             ["Puntos usados para trazar la línea", _puntos_linea(c)],
             ["Separación de la línea respecto al centro", _separacion_linea(c, r["geo"])],
             ["Ancho promedio de un orificio", f"{ancho:.1f}°"]]
    tabla = vz.tabla(filas, ["Medición", "Valor"])
    return vz.polar_bandas(c), vz.perfil(c), vz.espectro(c), tabla


def _resumen_clases(cls):
    nombres = [SENCILLO_A[a] for a in cls["clases_A"] if a != "A0"]
    if cls["clase_B"] == "B1":
        nombres.append(SENCILLO_B["B1"])
    return ", ".join(nombres) if nombres else "Sin defectos"


def panel_resultado(r):
    cls = r["cls"]
    v = cls["veredicto"]
    css = "NO" if v.startswith("NO") else v
    if v == "NO DIAGNOSTICABLE":
        titulo, sub = "No se puede diagnosticar", html.escape("; ".join(cls["motivos"]))
    else:
        titulo, sub = v.capitalize(), html.escape(_resumen_clases(cls))
    cab = f'<div class="ed-veredicto ed-v-{css}"><h2>{titulo}</h2><p>{sub}</p></div>'
    if cls["defectos"]:
        lis = "".join(
            f'<li><span class="ed-cod {d["clase"]}">{d["etiqueta"] or "!"}</span>'
            f'<span>{html.escape(d["texto"])}</span></li>' for d in cls["defectos"])
        cuerpo = f'<ul class="ed-defectos">{lis}</ul>'
    elif v == "CORRECTO":
        cuerpo = f'<p class="ed-nota">Los {C.N0} orificios tienen el ancho correcto y no hay manchas.</p>'
    else:
        cuerpo = ""
    adv = "".join(f'<p class="ed-nota">⚠ {html.escape(a)}</p>' for a in cls.get("advertencias", []))
    nota = ""
    if cls["defectos"]:
        nota = ('<p class="ed-nota ed-etiquetas">Etiqueta de errores: '
                '<span class="ed-cod A1">S</span> sector ausente '
                '<span class="ed-cod A2">E</span> ancho incorrecto '
                '<span class="ed-cod B1">M</span> mancha</p>')
    resumen = ""
    if "car" in r:
        c = r["car"]
        resumen = datos([("orificios encontrados", c["N"]), ("sectores tapados", c["N_azul"]),
                         ("manchas rojas", len(c["manchas"])),
                         ("ángulo de la línea de referencia", _angulo_ref(c)),
                         ("ruido", r["rui"]["nivel"]),
                         ("tiempo de análisis", f"{r['tiempos'].get('total', 0):.1f} s")])
        img = vz.anotada(r["rui"]["I_f"], c, cls)
    else:
        img = None
    return cab + resumen + datos_ubicacion(r["geo"]), cuerpo + adv + nota, img


# ------------------------------------------------------------------ lógica

def construir():
    tema = gr.themes.Base(
        primary_hue=gr.themes.Color(c50="#eef0fc", c100="#dde1f9", c200="#bcc3f3", c300="#9aa5ed",
                                    c400="#6775e1", c500="#3446d4", c600="#2a39b3", c700="#212d8d",
                                    c800="#192268", c900="#111744", c950="#0a0e2b"),
        neutral_hue="slate",
        font=[gr.themes.GoogleFont("Archivo"), "system-ui", "sans-serif"],
        radius_size="md",
    )
    kw_estilo = {"theme": tema, "css": CSS}
    bloques_kw = kw_estilo if GR_MAYOR < 6 else {}

    with gr.Blocks(title="Diagnóstico de codificador", **bloques_kw) as app:
        gr.HTML('<div id="ed-cabecera"><h1>Diagnóstico de codificador óptico</h1>'
                '<p>Sube una foto del disco sobre fondo negro. El sistema lo localiza, revisa que la '
                'imagen sea legible, cuenta los orificios y busca sectores faltantes, anchos incorrectos o manchas.</p></div>')

        with gr.Row(equal_height=False):
            with gr.Column(scale=4, min_width=300):
                archivo = gr.File(label="Foto del disco (JPG o PNG)", file_types=list(adquisicion.EXTENSIONES),
                                  type="filepath")
                boton = gr.Button("Diagnosticar", variant="primary", size="lg")
                progreso = gr.HTML(anillo(ESTADO_INICIAL, "", "esperando foto"))
                with gr.Accordion("Opciones", open=False):
                    filtro = gr.Radio([("Conserva bordes (bilateral)", "bilateral"), ("Gaussiano", "gaussiano")],
                                      value=C.FILTRO, label="Filtro para limpiar ruido",
                                      info="El gaussiano solo se usa para comparar resultados.")
                ejemplos = sorted(e for e in glob.glob(os.path.join(FOTOS, "**", "*"), recursive=True)
                                  if e.lower().endswith(adquisicion.EXTENSIONES))
                if ejemplos:
                    elegidos = []
                    for carpeta in sorted({os.path.dirname(e) for e in ejemplos}):
                        grupo = sorted(e for e in ejemplos if os.path.dirname(e) == carpeta)
                        elegidos.append(grupo[min(1, len(grupo) - 1)])
                    gr.Examples([[e] for e in elegidos[:16]], inputs=[archivo], label="Fotos de ejemplo",
                                example_labels=[os.path.relpath(os.path.dirname(e), FOTOS) for e in elegidos[:16]])

            with gr.Column(scale=8, min_width=420):
                with gr.Tabs(selected="t4") as tabs:
                    with gr.Tab("Resultado", id="t4"):
                        res_html = gr.HTML(vacio("Sube una foto y pulsa Diagnosticar. Aquí verás primero el disco "
                                                 "ubicado en la foto y después los defectos encontrados."))
                        with gr.Row(equal_height=False):
                            with gr.Column(min_width=300):
                                res_seg = gr.Image(label="1. Disco ubicado en la foto", interactive=False, height=460)
                                gr.HTML(LEYENDA)
                            with gr.Column(min_width=300):
                                res_img = gr.Image(label="2. Defectos encontrados", interactive=False, height=460)
                        res_def = gr.HTML(vacio("Lista de defectos con su ubicación."))
                    with gr.Tab("Ruido", id="t1"):
                        rui_dat = gr.HTML(vacio("Cuánto ruido tiene la foto y si se limpió."))
                        rui_img = gr.Image(label="Disco enderezado: antes y después de limpiar el ruido (con acercamiento ×4)", interactive=False)
                    with gr.Tab("Calidad de la foto", id="t2"):
                        val_html = gr.HTML(vacio("Se revisa si la foto tiene la calidad necesaria para diagnosticar."))
                    with gr.Tab("Mediciones", id="t3"):
                        car_pol = gr.Image(label="Vista del disco en polar", interactive=False)
                        car_per = gr.Image(label="Visualización de cambios disco / orificio", interactive=False)
                        with gr.Row():
                            car_esp = gr.Image(label="Espectro de frecuencias", interactive=False, scale=1)
                            car_tab = gr.HTML(vacio("Resumen de lo que se midió en el disco."))

        salidas = [progreso, tabs, rui_dat, rui_img, val_html,
                   car_pol, car_per, car_esp, car_tab, res_html, res_seg, res_img, res_def]

        def procesar(ruta, filtro_sel):
            if not ruta:
                yield {progreso: anillo(ESTADO_INICIAL, "", "sube una foto primero")}
                return
            estado = dict(ESTADO_INICIAL)
            estado["segmentacion"] = "activo"
            limpiar = {rui_img: None, car_pol: None, car_per: None, car_esp: None, res_img: None, res_seg: None,
                       rui_dat: vacio(""), val_html: vacio(""), car_tab: vacio(""),
                       res_html: vacio("Localizando el disco…"), res_def: vacio("")}
            yield {progreso: anillo(estado, "", "procesando", True), tabs: gr.Tabs(selected="t4"), **limpiar}

            try:
                for etapa, r in pipeline.ejecutar(ruta, filtro_sel):
                    salida = {}
                    if etapa == "segmentacion":
                        img, cab = panel_segmentacion(r)
                        salida.update({res_seg: img, res_html: cab})
                        estado["segmentacion"] = "hecho" if r["geo"]["ok"] else "fallo"
                        if r["geo"]["ok"]:
                            estado["ruido"] = "activo"
                    elif etapa == "ruido":
                        dat, img = panel_ruido(r)
                        salida.update({rui_dat: dat, rui_img: img})
                        estado["ruido"] = "hecho"
                        estado["validacion"] = "activo"
                    elif etapa == "validacion":
                        salida[val_html] = panel_validacion(r)
                        estado["validacion"] = "hecho" if r["val"]["pasa"] else "fallo"
                        if r["val"]["pasa"]:
                            estado["caracteristicas"] = "activo"
                        else:
                            for k in ("caracteristicas", "resultado"):
                                estado[k] = "omitido"
                            txt, lista, _ = panel_resultado(r)
                            salida.update({res_html: txt, res_def: lista})
                            salida[car_tab] = vacio("La imagen no pasó la validación: no se extraen características.")
                            yield {**salida, progreso: anillo(estado, "Foto no apta", "ver calidad",
                                                             final="NO"),
                                   tabs: gr.Tabs(selected="t2")}
                            return
                    elif etapa == "caracteristicas":
                        pol, per, esp, tab = panel_caracteristicas(r)
                        salida.update({car_pol: pol, car_per: per, car_esp: esp, car_tab: tab})
                        estado["caracteristicas"] = "hecho"
                        estado["resultado"] = "activo"
                    elif etapa == "resultado":
                        txt, lista, img = panel_resultado(r)
                        salida.update({res_html: txt, res_img: img, res_def: lista})
                        estado["resultado"] = "hecho"
                        v = r["cls"]["veredicto"]
                        n_def = len(r["cls"]["defectos"])
                        clases = "sin defectos" if n_def == 0 else f"{n_def} defecto{'s' if n_def > 1 else ''}"
                        yield {**salida, progreso: anillo(estado, v.capitalize(), clases, final=v),
                               tabs: gr.Tabs(selected="t4")}
                        return
                    yield {**salida, progreso: anillo(estado, "", "procesando", True),
                           tabs: gr.Tabs(selected=TAB_DE[etapa])}
            except Exception as e:  # mensaje claro en vez de un traceback en la interfaz
                activo = next((k for k, s in estado.items() if s == "activo"), "segmentacion")
                estado[activo] = "fallo"
                yield {progreso: anillo(estado, "Error", activo),
                       res_html: vacio(f"No se pudo procesar la imagen: {html.escape(str(e))}")}

        boton.click(procesar, [archivo, filtro], salidas)
        archivo.upload(lambda: anillo(ESTADO_INICIAL, "", "listo para diagnosticar"), None, progreso)

    return app, kw_estilo


if __name__ == "__main__":
    if os.path.isdir(FOTOS) and hasattr(gr, "set_static_paths"):
        gr.set_static_paths(paths=[FOTOS])
    app, kw_estilo = construir()
    lanzar = {"inbrowser": True, "allowed_paths": [FOTOS] if os.path.isdir(FOTOS) else []}
    if GR_MAYOR >= 6:
        lanzar.update(kw_estilo)
    if os.environ.get("ED_SIN_NAVEGADOR"):
        lanzar["inbrowser"] = False
    app.queue().launch(**lanzar)
