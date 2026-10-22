"""Estilo compartido por las dos aplicaciones de Gradio."""
import gradio as gr

GR_MAYOR = int(gr.__version__.split(".")[0])   # Gradio 6 recibe tema y CSS en launch(), Gradio 5 en Blocks()

CSS = """
:root, .dark {
  --ed-tinta: #1d2430; --ed-gris: #8a93a3; --ed-linea: #dfe3ea; --ed-fondo: #ffffff;
  --ed-azul: #3446d4; --ed-rojo: #d23b3b; --ed-verde: #1f8a5b; --ed-ambar: #c98a12;
  --ed-suave: #f3f5f8;
}
.dark {
  --ed-tinta: #e9edf3; --ed-gris: #8f98a8; --ed-linea: #343b47; --ed-fondo: #1a1e24;
  --ed-suave: #222831;
}
.gradio-container { max-width: 1320px !important; }
#ed-cabecera { padding: 6px 2px 2px; }
#ed-cabecera h1 { font-size: 1.65rem; font-weight: 700; letter-spacing: -0.01em; margin: 0;
  color: var(--ed-tinta); }
#ed-cabecera p { color: var(--ed-gris); margin: 4px 0 0; font-size: 0.95rem; max-width: 70ch; }

.ed-anillo { display: flex; gap: 18px; align-items: center; padding: 8px 4px; }
.ed-anillo svg { flex: 0 0 168px; }
.ed-pasos { list-style: none; margin: 0; padding: 0; font-size: 0.92rem; }
.ed-pasos li { display: flex; align-items: center; gap: 8px; padding: 3px 0; color: var(--ed-gris); }
.ed-pasos li .p { width: 9px; height: 9px; border-radius: 50%; background: var(--ed-linea); flex: none; }
.ed-pasos li.hecho { color: var(--ed-tinta); }
.ed-pasos li.hecho .p { background: var(--ed-tinta); }
.ed-pasos li.activo { color: var(--ed-azul); font-weight: 600; }
.ed-pasos li.activo .p { background: var(--ed-azul); box-shadow: 0 0 0 4px color-mix(in srgb, var(--ed-azul) 22%, transparent); }
.ed-pasos li.fallo { color: var(--ed-rojo); font-weight: 600; }
.ed-pasos li.fallo .p { background: var(--ed-rojo); }
@media (prefers-reduced-motion: no-preference) {
  .ed-giro { transform-origin: 84px 84px; animation: ed-giro 1.6s linear infinite; }
  @keyframes ed-giro { to { transform: rotate(360deg); } }
}

.ed-datos { display: flex; flex-wrap: wrap; gap: 8px; margin: 2px 0 6px; }
.ed-dato { border: 1px solid var(--ed-linea); border-radius: 10px; padding: 7px 12px; min-width: 96px;
  background: var(--ed-fondo); }
.ed-dato b { display: block; font-size: 1.15rem; color: var(--ed-tinta); font-variant-numeric: tabular-nums; }
.ed-dato span { font-size: 0.78rem; color: var(--ed-gris); }

.ed-tabla { width: 100%; border-collapse: collapse; font-size: 0.92rem; font-variant-numeric: tabular-nums; }
.ed-tabla th { text-align: left; font-weight: 600; color: var(--ed-gris); padding: 6px 10px;
  border-bottom: 1px solid var(--ed-linea); font-size: 0.82rem; }
.ed-tabla td { padding: 7px 10px; border-bottom: 1px solid var(--ed-linea); color: var(--ed-tinta); }
.ed-ok { color: var(--ed-verde); font-weight: 700; }
.ed-no { color: var(--ed-rojo); font-weight: 700; }

.ed-veredicto { border-radius: 14px; padding: 16px 18px; margin-bottom: 10px; color: #fff; }
.ed-veredicto h2 { margin: 0; font-size: 1.5rem; letter-spacing: 0.01em; color: #fff; }
.ed-veredicto p { margin: 4px 0 0; opacity: 0.92; color: #fff; }
.ed-v-CORRECTO { background: var(--ed-verde); }
.ed-v-DEFECTUOSO { background: var(--ed-rojo); }
.ed-v-NO { background: #5b6372; }
.ed-defectos { list-style: none; margin: 6px 0 0; padding: 0; }
.ed-defectos li { padding: 8px 0; border-bottom: 1px solid var(--ed-linea); color: var(--ed-tinta);
  display: flex; gap: 10px; align-items: baseline; }
.ed-cod { font-weight: 700; font-size: 0.8rem; border-radius: 6px; padding: 1px 7px; color: #fff; flex: none;
  min-width: 2.2em; text-align: center; }
.ed-cod.A1 { background: var(--ed-azul); }
.ed-cod.A2 { background: #f2c200; color: #1d2430; }
.ed-cod.A3, .ed-cod.A9 { background: #6b4fc8; } .ed-cod.B1 { background: var(--ed-rojo); }
.ed-desc { color: var(--ed-gris); font-size: 0.8rem; margin-top: 2px; max-width: 46ch; }
.ed-tabla td b { font-weight: 600; }
.ed-sub { color: var(--ed-gris); font-size: 0.82rem; margin: 10px 0 4px; }
.ed-chico .ed-dato { padding: 5px 10px; min-width: 80px; }
.ed-chico .ed-dato b { font-size: 0.95rem; }
.ed-espera { background: #5b6372; }
.ed-leyenda { display: flex; margin-bottom: 8px; flex-wrap: wrap; gap: 6px 16px; font-size: 0.8rem; color: var(--ed-gris); padding: 4px 2px; }
.ed-leyenda span { display: inline-flex; align-items: center; gap: 6px; }
.ed-leyenda i { width: 14px; height: 10px; border-radius: 3px; display: inline-block; }
.ed-etiquetas { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 8px; }
.ed-etiquetas .ed-cod { min-width: 1.6em; margin-left: 6px; }
.ed-nota { color: var(--ed-gris); font-size: 0.85rem; margin-top: 8px; }
.ed-vacio { color: var(--ed-gris); padding: 28px 6px; }
"""
