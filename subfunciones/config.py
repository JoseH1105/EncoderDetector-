"""
Parámetros del sistema (v1.4, sección 8.1).

Todos los módulos leen sus umbrales de aquí. Los marcados [calibrar] se
sobrescriben con datos/calibracion.json, que genera calibrar.py. Si el JSON
no existe se usan los valores iniciales.
"""
import json
import os

# ---------------------------------------------------------------- rutas
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # carpeta del proyecto
DIR_DATOS = os.path.join(RAIZ, "datos")
DIR_SALIDAS = os.path.join(DIR_DATOS, "salidas_calibracion")
DIR_FOTOS = os.path.abspath(os.path.join(RAIZ, "..", "Fotos T2"))     # fotos de ejemplo y de calibración
RUTA_CALIBRACION = os.path.join(DIR_DATOS, "calibracion.json")

# ---------------------------------------------------------------- disco físico
# Foto de referencia para el diámetro aparente (ver escala.py)
REF_IMAGEN = "referencia_escala.jpg"
REF_DIAMETRO_MM = 59.5
ANCHO_NATIVO, ALTO_NATIVO = 4752, 3168   # resolución de la cámara (px)
TOLERANCIA_ASPECTO = 0.01   # misma proporción que la nativa (±1 %) → la imagen se toma como reducida
N0 = 12                     # huecos del disco correcto

# ---------------------------------------------------------------- bloque 1
LADO_LOC = 1600             # lado largo de la imagen reducida (px)

# ---------------------------------------------------------------- bloque 2
KERNEL_MORF = 7             # elipse 7x7 para apertura/cierre [calibrar]
AREA_MIN_CONTORNO = 0.005   # fracción del área de la imagen (0,5 %)
C_MIN = 0.80                # circularidad mínima
MARGEN_BORDE = 2            # px (en I_loc) para decidir "disco completo"

# ---------------------------------------------------------------- bloque 3
DN = 1000                   # diámetro normalizado (px)
LADO_N = 1100               # lado de la imagen normalizada (px)

# ---------------------------------------------------------------- bloque 4
SIGMA_CAMARA = 1.5          # σ̂ por debajo de esto no se filtra [calibrar]
SIGMA_ALTO = 5.0            # corte medio/alto del nivel de ruido [calibrar]
K_BILATERAL = 2.0           # σ_color = k·σ̂ [calibrar]
D_BILATERAL = 5
SIGMA_ESPACIO = 3.0
FILTRO = "bilateral"        # "bilateral" | "gaussiano" (alternativa a comparar)
K_GAUSS = 0.25              # σ_gauss = k·σ̂ (solo alternativa)
GRAD_EXCLUIR_PCT = 90       # σ̂: se excluyen bordes (percentil del gradiente)

# ---------------------------------------------------------------- bloque 5
D_MIN = 400                 # px originales
THETA_MAX = 30.0            # grados [calibrar con fotos nuevas]
THETA_MEDIA = 15.0          # corte baja/media de inclinación
ESCALA_ENFOQUE = 0.25       # F se mide sobre I_f reducida (ver validacion.enfoque)
F_MIN = 2.5                 # enfoque [calibrar]
F_BUENO = 6.0               # corte aceptable/bueno [calibrar]
ETA_MIN = 0.60              # separabilidad de Otsu [calibrar]
ETA_ALTO = 0.80             # corte medio/alto
NIVEL_SATURADO = 254        # píxel recortado: los 3 canales ≥ este nivel
SAT_MARCA_MAX = 30.0        # % saturado en la banda de la marca [calibrar]
SAT_MARCA_ALTA = 10.0       # corte correcta/alta
Z_MIN = 6.0                 # puntaje mínimo de la marca [calibrar]

# ---------------------------------------------------------------- bloque 6
POLAR_ANG = 720             # filas (0,5° por fila)
POLAR_RAD = 200             # columnas (0..R)
BANDA_MARCA = (0.25, 0.40)
BANDA_CORONA = (0.44, 0.92)
BANDA_MUESTREO = (0.54, 0.83)
TRAMO_MIN = 4               # muestras (2°)
K_RANGO = (4, 40)
H_AZUL = (100, 160)         # OpenCV, H en 0..180 (azul a violeta)
S_ACROMATICO = 40           # por debajo el tono no es fiable: se acepta la fila si no es roja
H_ROJO = (10, 165)          # rojo: H < 10 o H > 165
S_MIN = 60                  # material / azul [calibrar]
S_ROJO = 70                 # manchas [calibrar]
MAD_PISO = 2.0
SUAVIZADO_MARCA = 5         # muestras
# Línea de referencia: un punto por banda (dos interiores y uno en el borde) y una recta por ellos
BANDAS_LINEA = ((0.15, 0.24), (0.32, 0.41), (0.935, 0.975))
VENTANA_LINEA = 5.0         # ± grados alrededor del ángulo inicial donde se busca cada punto
Z_PUNTO_MIN = 2.0           # puntaje mínimo para usar un punto en el ajuste
W_AZUL_MIN = 4.0            # grados [calibrar]
FRAC_AZUL_FILA = 0.5        # fracción de la fila en banda que debe ser azul
V_COLOR_FRAC = 0.50         # S solo cuenta si V > V_COLOR_FRAC·t_c (en el fondo negro S es ruido)
KERNEL_MANCHA = 5
A_MIN = 0.15                # % del área del disco [calibrar]

# ---------------------------------------------------------------- bloque 7
W_H0 = None                 # ancho nominal de hueco (°) [calibrar]
W_H_TOL = None              # tolerancia ±3σ (°) [calibrar]
W_B0 = None                 # ancho nominal de barra entre orificios (°) [calibrar]
W_B_TOL = None              # tolerancia ±3σ (°) [calibrar]

# ---------------------------------------------------------------- generador
SIGMA_DISENO = (5.0, 20.0)
SIGMA_PRUEBA = (20.0, 40.0)
VARIANTES = 3
CALIDAD_JPG = 95


def cargar_calibracion(ruta=RUTA_CALIBRACION):
    """Sobrescribe los parámetros con los de calibracion.json (si existe)."""
    if not os.path.exists(ruta):
        return {}
    with open(ruta, encoding="utf-8") as f:
        datos = json.load(f)
    valores = datos.get("valores", datos)
    g = globals()
    aplicados = {}
    for k, v in valores.items():
        if k in g and not k.startswith("_"):
            g[k] = tuple(v) if isinstance(g[k], tuple) else v
            aplicados[k] = v
    return aplicados


CALIBRACION_APLICADA = cargar_calibracion()
