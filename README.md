# Optical encoder disc diagnosis (v1.4)

**[English](#english) · [Español](#español)**

<p align="center">
  <img src="ejemplos/Luz%20directa/Normales/IMG_0809.JPG" width="32%" alt="Correct disc, direct light">
  <img src="ejemplos/Luz%20directa/Manchas/IMG_0830.JPG" width="32%" alt="Disc with red stains">
  <img src="ejemplos/Campo%20oscuro/Normales/IMG_0951.JPG" width="32%" alt="Dark field">
</p>

---

<a id="english"></a>

## English

A computer vision system that inspects an encoder disc from a photo: it locates the disc, checks that the image is readable, counts the slots, finds the blue reference mark and detects missing sectors, wrong widths, added sectors and red stains. It implements the specification `solucion_diagnostico_encoder_v1.4.md`.

The source code, the user interface and the data files are in Spanish; this section explains them in English.

### Installation

Python 3.10 or newer. In any virtual environment (venv, conda, …):

```bash
pip install -r requirements.txt
```

Tested with Python 3.13, OpenCV 5.0 and Gradio 6.29. The code also works with Gradio 5.

### Quick start

From the project folder:

```bash
python app_diagnostico.py         # diagnosis app (http://127.0.0.1:7860)
python app_generador_ruido.py     # noise generator (http://127.0.0.1:7861)
```

In the app, upload a JPG or PNG photo and press **Diagnosticar**. The tabs fill in stage by stage. If the image fails validation, the process stops at that tab and shows the reason. The app offers one example photo per condition from the `ejemplos/` folder.

To use your own photo set instead, point the `ENCODER_FOTOS` environment variable at a folder whose subfolders are the capture conditions:

```bash
ENCODER_FOTOS=/path/to/my_photos python app_diagnostico.py
```

On Windows PowerShell: `$env:ENCODER_FOTOS = "C:\path\to\my_photos"` before running the app.

### Example photos

`ejemplos/` contains one photo per capture condition (metadata removed). Subfolder names are the conditions used during calibration:

| Folder | Condition |
|---|---|
| `Luz difusa` | Diffuse light |
| `Luz directa/Normales`, `Luz directa/Manchas` | Direct light, clean disc / with red stains |
| `Campo oscuro/Normales`, `Campo oscuro/Manchadas` | Dark field, clean / with stains |
| `Desenfocadas` | Out of focus (should be rejected) |
| `Inclinación/Normal`, `Inclinación/Manchas`, `Inclinación/Menos 30` | Tilted disc (~40°, and less than 30°) |
| `Largo` | Taken from far away |
| `Mala iluminación/Luz directa`, `…/Mucho brillo`, `…/Oscuras` | Poor lighting: harsh light, overexposed, dark |
| `Fondo con textura` | Textured background |
| `Ruido añadido` | Synthetic Gaussian noise (σ ≈ 36), made with the noise generator |
| `Casos de error` | Cases where the system is expected to fail |

### Structure

```
encoder_diag_entrega/
├── app_diagnostico.py          # diagnosis app (port 7860)
├── app_generador_ruido.py      # separate noise generator app (port 7861)
├── calibrar.py                 # batch measurement and threshold rules
├── requirements.txt
├── ejemplos/                   # example photos, one per condition
├── subfunciones/               # blocks 1 to 7 and utilities
│   ├── config.py
│   ├── adquisicion.py … clasificacion.py
│   ├── escala.py, pipeline.py, visualizacion.py
│   └── estilo_interfaz.py      # CSS shared by both apps
└── datos/
    ├── calibracion.json        # calibrated thresholds and the rule behind each one
    ├── referencia_escala.jpg / .json
    └── salidas_calibracion/    # labels, measurements, results, noise sweep and plots
```

The apps and `calibrar.py` are run from the project root; the modules in `subfunciones/` are not run on their own. All paths are relative to the project folder (see `subfunciones/config.py`).

| File | Block | What it does |
|---|---|---|
| `subfunciones/config.py` | | All parameters and paths. Reads `datos/calibracion.json` on import |
| `adquisicion.py` | 1 | JPG or PNG photo → `I0` and `I_loc` (1600 px); rejects other formats with a clear message |
| `segmentacion.py` | 2 | V channel, Otsu + η, morphology, most circular contour, `fitEllipse` |
| `normalizacion.py` | 3 | Affine ellipse → circle, DN = 1000 px, 1100 × 1100 crop |
| `ruido.py` | 4 | Immerkaer σ̂ and self-tuned bilateral filter (Gaussian as an alternative) |
| `validacion.py` | 5 | Quality criteria with value, threshold, level and ✓/✗ |
| `caracteristicas.py` | 6 | Polar image, mark, profile p(θ), DFT, blue blocks, stains |
| `clasificacion.py` | 7 | Axes A/B and verdict |
| `escala.py` | | Reference scale and apparent diameter (`datos/referencia_escala.jpg`, 59.5 mm) |
| `pipeline.py` | | `ejecutar()` (generator for the app), `analizar()`, `medir()` |
| `visualizacion.py` | | Annotated images, plots and tables |
| `estilo_interfaz.py` | | CSS and Gradio version, shared by both apps |
| `app_diagnostico.py` | | System interface |
| `app_generador_ruido.py` | | Separate app: ZIP with JPG + CSV |
| `calibrar.py` | | Batch measurement and threshold rules |

### Calibration

```bash
python calibrar.py todo --fotos <photo_folder>             # labels + measure + thresholds + review
python calibrar.py ruido --zip ruido_diseno_YYYYMMDD.zip   # K_BILATERAL sweep
python calibrar.py color                                   # optional: samples with cv2.selectROI
```

Without `--fotos`, the folder from `ENCODER_FOTOS` (or `ejemplos/`) is used. Outputs go to `datos/salidas_calibracion/` and thresholds to `datos/calibracion.json`. The delivered calibration was made with the full set of 137 photos; `ejemplos/` holds only a sample of it.

| Step | Output |
|---|---|
| `etiquetas` | `etiquetas.csv`: condition (subfolder), design/test set (the 3rd shot of each trio goes to test), criterion that should fail and disc type |
| `medir` | `mediciones.csv`: every metric from blocks 1 to 6, without decisions |
| `umbrales` | `datos/calibracion.json`: values and the rule that produced each one |
| `revisar` | `resultados.csv` and `graficas/` (one plot per metric with its threshold) |
| `ruido` | `ruido_barrido.csv` and `K_BILATERAL` in `calibracion.json` |

**Check the `disco` column of `etiquetas.csv`.** The script fills it with a suggestion based on k\* and N_azul (`disco_origen = sugerido`). Until you correct it by hand, the axis A hits in `revisar` are partly circular. If you change a label, run `umbrales` and `revisar` again.

Rules used: if two groups do not overlap, the threshold is the midpoint between their extremes. If they overlap, the threshold with fewest errors is taken and, among ties, the centre of the widest gap. σ_camera is the 95th percentile of σ̂ plus 0.5. The width tolerance is 3σ of the slots of the correct disc. Reading levels use terciles.

### Delivered calibration v0 (137 photos, 93 for design)

| Parameter | Value | Note |
|---|---|---|
| F_MIN | 2.83 | Out of focus ≤ 1.53, rest ≥ 4.13. Separates |
| Z_MIN | 4.07 | Does not fully separate: IMG_1037 (overexposed) has a visible mark, z = 6.9 |
| SAT_MARCA_MAX | 24 % | Does not fully separate, see decisions |
| ETA_MIN | 0.60 | No bad-contrast photos; clean minimum 0.70 |
| SIGMA_CAMARA | 0.85 | |
| A_MIN | 0.13 % of the disc | |
| W_H0 ± W_H_TOL | 14.98° ± 1.67° | Slot width, 204 slots from 17 photos |
| W_B0 ± W_B_TOL | 15.02° ± 1.57° | Width of the bar between slots, same rule |
| K_BILATERAL | 2 | Tie on design. With the test batch (σ 20 to 40) K = 2 gets 17/18 and K ≥ 3 gets 18/18 |

`revisar` result: on diagnosable photos, axes A and B are 100 % correct on both design and test. All out-of-focus, tilted (~40°) and overexposed photos are rejected. 7 of the 17 "Largo" photos (the brightest shot of each trio) are also rejected because 86 % to 97 % of the mark band is clipped to white.

Still uncalibrated: THETA_MAX (photos at 15 to 20° are missing) and SIGMA_ALTO (a noise batch is missing to set the medium/high cut).

### Implementation decisions

Each one came from measuring the 137 photos. The values are in `config.py` and can be reverted.

1. **Colour only counts when there is brightness.** On the black background, S = (max − min)/max is pure noise and slots appeared as "coloured material". Material = V > t_c or (S > s_min and V > 0.50·t_c). The same applies to the blue and red masks (`V_COLOR_FRAC`). With this, dark field with stains went from N ≠ k\* in 6/12 to 0/12.
2. **Focus F at 1/4 scale** (`ESCALA_ENFOQUE`). At full scale, "Largo" photos (D0 from 430 to 600 px, upscaled ×2) gave F as low as the out-of-focus ones. At 1/4 scale F measures edge width and the groups separate with a ×2.7 margin. That is why F_MIN is no longer at the prototype's 0.19 scale.
3. **Saturation = all 3 channels ≥ 254** in the mark band. A high V alone does not mean the blue line is lost.
4. **Mark: robust reference without red rows.** A stain inside the band inflated the MAD of S and killed the z score. Median and MAD are computed without red-hue rows.
5. **σ̂: the gradient used to exclude edges is measured on the smoothed image.** Measured on the noisy image, it discards exactly the noisiest pixels.
6. **Width tolerance:** slots next to a blue block are not evaluated. Their edge is defined by the paint (in IMG_1001 one measured 19.5°).
7. **Wrong width also on bars.** On the "wrong width" disc the slots are within tolerance; what changes are three bars of ~25° (normal 15°). A2 is flagged if a slot or a bar falls outside its 3σ tolerance. With this, the width disc always gives 3 flagged gaps and the other discs none.
8. **Apparent diameter from a reference photo** (`escala.py`). The apparent size of the disc in the photo is reported, not the real one. `datos/referencia_escala.jpg` is the photo at the standard distance, where the disc measures 59.5 mm. Its diameter in pixels sets the scale (`px_por_mm`, 21.7 with the current reference), and in each photo the apparent diameter is D0 / px_por_mm. If the disc is closer it looks bigger and if it is further, smaller: "Largo" shots give 20–27 mm and tilted ones, closer to the camera, ~90 mm. All lengths are brought to pixels at the camera's native resolution (4752 × 3168): an image with the same aspect ratio and another width is treated as downscaled and rescaled; one with a different aspect ratio is treated as a crop. The reference measurement is stored in `referencia_escala.json` and is redone automatically if you change the image. For better precision, replace `referencia_escala.jpg` with the camera's original file.
9. **Reference line drawn through three points.** The initial angle comes from the mark band (0.25–0.40 R), and its score decides whether the mark is readable. Then the line is searched in three bands, ±5° around that angle: two in the inner white area (0.15–0.24 R and 0.32–0.41 R) and one on the outer edge, past the ring (0.935–0.975 R). Each point is refined with a parabola over the score and used if its score is ≥ 2. A line is fitted through the used points (`cv2.fitLine`), not forced through the centre. With fewer than two points the radial ray is used. On the 78 diagnosable photos: 65 with 3 points and 13 with 2; the angle changes 0.5° on average (max 3°) and the drawn line ends up about 3.5 px from the centre on average (max ~11 px). The defects image and the polar view draw the line and its points (white = used, grey = discarded).

### What the interface shows

The app has four tabs: Resultado (Result), Ruido (Noise), Calidad de la foto (Photo quality) and Mediciones (Measurements). Result shows two separate images: first the disc located in the original photo (green border, ring circles in white, blue band where slots are counted), which appears as soon as the disc is found, and then the straightened disc with the defects marked.

The app uses plain names (for example "orificios encontrados" instead of N, "ángulo de la línea de referencia" instead of θ_ref, "ruido medido" instead of σ̂). The quality tab explains what each criterion checks.

Each defect has the same label in the list and in the image: S1, S2… for missing sectors, E1, E2… for wrong widths (yellow box) and M1, M2… for stains (red box). Slots are numbered 1 to N counter-clockwise from the reference line.

### Notes for the report

- **Generated σ vs σ̂:** σ̂ ≈ 0.11·σ, much less than the 0.78 estimated in the prototype. Grey conversion weights the channels (×0.67), INTER_AREA down to DN averages (×0.45) and the bilinear `warpAffine` averages again (×0.5). Even so, the diagnosis stays the same as on the clean photo up to σ = 40 with K ≥ 3.
- **Canny vs relative contrast** (`datos/salidas_calibracion/graficas/marca_contraste_vs_canny.csv`): they agree (±3°) in 9/12 with diffuse light, 8/8 dark, 0/12 out of focus and 5/12 direct light with stains. This confirms the decision to drop Canny.
- **Alternatives implemented** for study 6.1: `segmentacion.localizar_hough`, `caracteristicas.marca_canny`, `caracteristicas.contar_componentes` and the Gaussian filter (option in the app). `mediciones.csv` already includes `theta_canny` and `N_componentes`.
- **Limitations:** a stain over a slot is not visible. With overexposure red loses saturation. The 16-slot disc at ~40° loses slots because of the acrylic thickness.

### To do

- Photos at 15 to 20° to set THETA_MAX, and distance photos with full framing.
- Textured background.
- Webcam capture: only the image source in `adquisicion.py` changes.

---

<a id="español"></a>

## Español

Sistema de visión que revisa un disco codificador a partir de una foto: lo localiza, comprueba que la imagen sea legible, cuenta los huecos, encuentra la marca azul de referencia y detecta sectores ausentes, anchos incorrectos, sectores añadidos y manchas rojas. Implementa la especificación `solucion_diagnostico_encoder_v1.4.md`.

### Instalación

Python 3.10 o posterior. En cualquier entorno virtual (venv, conda, …):

```bash
pip install -r requirements.txt
```

Probado con Python 3.13, OpenCV 5.0 y Gradio 6.29. El código también funciona con Gradio 5.

### Uso rápido

Desde la carpeta del proyecto:

```bash
python app_diagnostico.py         # app del sistema (http://127.0.0.1:7860)
python app_generador_ruido.py     # generador de ruido (http://127.0.0.1:7861)
```

En la app sube una foto JPG o PNG y pulsa **Diagnosticar**. Las pestañas se llenan etapa por etapa. Si la imagen no pasa la validación, el proceso se detiene en esa pestaña y muestra el motivo. La app ofrece una foto de ejemplo por condición, tomada de la carpeta `ejemplos/`.

Para usar tu propio conjunto de fotos, define la variable de entorno `ENCODER_FOTOS` con una carpeta cuyas subcarpetas sean las condiciones de captura:

```bash
ENCODER_FOTOS=/ruta/a/mis_fotos python app_diagnostico.py
```

En PowerShell de Windows: `$env:ENCODER_FOTOS = "C:\ruta\a\mis_fotos"` antes de abrir la app.

### Fotos de ejemplo

`ejemplos/` trae una foto por condición de captura (sin metadatos). Los nombres de las subcarpetas son las condiciones usadas en la calibración: luz difusa, luz directa (normales y con manchas), campo oscuro (normales y manchadas), desenfocadas, inclinación (normal, con manchas y menos de 30°), largo, mala iluminación (luz directa, mucho brillo y oscuras), fondo con textura, ruido añadido (σ ≈ 36, hecho con el generador) y casos de error.

### Estructura

```
encoder_diag_entrega/
├── app_diagnostico.py          # app del sistema (puerto 7860)
├── app_generador_ruido.py      # app aparte del generador de ruido (puerto 7861)
├── calibrar.py                 # medición por lotes y reglas de umbral
├── requirements.txt
├── ejemplos/                   # fotos de ejemplo, una por condición
├── subfunciones/               # bloques 1 a 7 y utilidades
│   ├── config.py
│   ├── adquisicion.py … clasificacion.py
│   ├── escala.py, pipeline.py, visualizacion.py
│   └── estilo_interfaz.py      # CSS compartido por las dos apps
└── datos/
    ├── calibracion.json        # umbrales calibrados y la regla de cada uno
    ├── referencia_escala.jpg / .json
    └── salidas_calibracion/    # etiquetas, mediciones, resultados, barrido de ruido y gráficas
```

Las apps y `calibrar.py` se ejecutan desde la raíz del proyecto; los módulos de `subfunciones/` no se ejecutan solos. Todas las rutas son relativas a la carpeta del proyecto (ver `subfunciones/config.py`).

| Archivo | Bloque | Qué hace |
|---|---|---|
| `subfunciones/config.py` | | Todos los parámetros y rutas. Lee `datos/calibracion.json` al importar |
| `adquisicion.py` | 1 | Foto JPG o PNG → `I0` e `I_loc` (1600 px); rechaza otros formatos con un mensaje claro |
| `segmentacion.py` | 2 | Canal V, Otsu + η, morfología, contorno de mayor circularidad, `fitEllipse` |
| `normalizacion.py` | 3 | Afín elipse → círculo, DN = 1000 px, recorte de 1100 × 1100 |
| `ruido.py` | 4 | σ̂ de Immerkaer y bilateral autoajustado (gaussiano como alternativa) |
| `validacion.py` | 5 | Criterios de calidad con valor, umbral, nivel y ✓/✗ |
| `caracteristicas.py` | 6 | Imagen polar, marca, perfil p(θ), DFT, bloques azules, manchas |
| `clasificacion.py` | 7 | Ejes A/B y veredicto |
| `escala.py` | | Escala de referencia y diámetro aparente (`datos/referencia_escala.jpg`, 59,5 mm) |
| `pipeline.py` | | `ejecutar()` (generador para la app), `analizar()`, `medir()` |
| `visualizacion.py` | | Imágenes anotadas, gráficas y tablas |
| `estilo_interfaz.py` | | CSS y versión de Gradio, compartidos por las dos apps |
| `app_diagnostico.py` | | Interfaz del sistema |
| `app_generador_ruido.py` | | Aplicación aparte: ZIP con JPG + CSV |
| `calibrar.py` | | Medición por lotes y reglas de umbral |

### Calibración

```bash
python calibrar.py todo --fotos <carpeta_fotos>            # etiquetas + medir + umbrales + revisar
python calibrar.py ruido --zip ruido_diseno_AAAAMMDD.zip   # barrido de K_BILATERAL
python calibrar.py color                                   # opcional: muestras con cv2.selectROI
```

Sin `--fotos` se usa la carpeta de `ENCODER_FOTOS` (o `ejemplos/`). Las salidas quedan en `datos/salidas_calibracion/` y los umbrales en `datos/calibracion.json`. La calibración entregada se hizo con el conjunto completo de 137 fotos; `ejemplos/` solo trae una muestra.

| Paso | Salida |
|---|---|
| `etiquetas` | `etiquetas.csv`: condición (subcarpeta), conjunto diseño/prueba (el 3.er disparo de cada trío va a prueba), criterio que debería fallar y tipo de disco |
| `medir` | `mediciones.csv`: todas las métricas de los bloques 1 a 6, sin decidir |
| `umbrales` | `datos/calibracion.json`: valores y la regla que produjo cada uno |
| `revisar` | `resultados.csv` y `graficas/` (una gráfica por métrica con su umbral) |
| `ruido` | `ruido_barrido.csv` y `K_BILATERAL` en `calibracion.json` |

**Revisa la columna `disco` de `etiquetas.csv`.** El script la llena con una sugerencia a partir de k\* y N_azul (`disco_origen = sugerido`). Mientras no la corrijas a mano, los aciertos del eje A en `revisar` son en parte circulares. Si cambias una etiqueta, vuelve a correr `umbrales` y `revisar`.

Reglas usadas: si dos grupos no se traslapan, el umbral es el punto medio entre sus extremos. Si se traslapan, se toma el umbral con menos errores y, entre empates, el centro del hueco más ancho. σ_cámara es el percentil 95 de σ̂ más 0,5. La tolerancia de ancho es 3σ de los huecos del disco correcto. Los niveles de lectura usan terciles.

### Calibración v0 entregada (137 fotos, 93 de diseño)

| Parámetro | Valor | Nota |
|---|---|---|
| F_MIN | 2,83 | Desenfocadas ≤ 1,53, resto ≥ 4,13. Separa |
| Z_MIN | 4,07 | No separa del todo: IMG_1037 (mucho brillo) tiene la marca visible, z = 6,9 |
| SAT_MARCA_MAX | 24 % | No separa del todo, ver decisiones |
| ETA_MIN | 0,60 | Sin fotos de contraste malo; mínimo limpio 0,70 |
| SIGMA_CAMARA | 0,85 | |
| A_MIN | 0,13 % del disco | |
| W_H0 ± W_H_TOL | 14,98° ± 1,67° | Ancho de orificio, 204 orificios de 17 fotos |
| W_B0 ± W_B_TOL | 15,02° ± 1,57° | Ancho de la barra entre orificios, misma regla |
| K_BILATERAL | 2 | Empate en diseño. Con el lote de prueba (σ 20 a 40) K = 2 acierta 17/18 y K ≥ 3 acierta 18/18 |

Resultado de `revisar`: en las fotos diagnosticables, los ejes A y B aciertan el 100 % tanto en diseño como en prueba. Se rechazan todas las desenfocadas, las inclinadas (~40°) y las de mucho brillo. También se rechazan 7 de las 17 fotos "Largo" (el disparo más claro de cada trío) porque entre el 86 % y el 97 % de la banda de la marca está recortada a blanco.

Quedan sin calibrar THETA_MAX (faltan fotos a 15 a 20°) y SIGMA_ALTO (falta un lote de ruido para fijar el corte medio/alto).

### Decisiones tomadas al implementar

Cada una salió de medir las 137 fotos. Los valores están en `config.py` y se pueden revertir.

1. **El color solo cuenta si hay brillo.** En el fondo negro, S = (max − min)/max es ruido puro y los huecos aparecían como "material de color". Material = V > t_c o (S > s_min y V > 0,50·t_c). Lo mismo aplica a la máscara azul y a la roja (`V_COLOR_FRAC`). Con esto, campo oscuro con manchas pasó de N ≠ k\* en 6/12 a 0/12.
2. **Enfoque F a 1/4 de escala** (`ESCALA_ENFOQUE`). A escala completa, las fotos "Largo" (D0 de 430 a 600 px, ampliadas al doble) daban F tan bajo como las desenfocadas. A 1/4 de escala F mide el ancho del borde y los grupos se separan con margen ×2,7. Por eso F_MIN ya no está en la escala 0,19 del prototipo.
3. **Saturación = los 3 canales ≥ 254** en la banda de la marca. Un V alto por sí solo no implica que la línea azul se pierda.
4. **Marca: referencia robusta sin filas rojas.** Una mancha dentro de la banda inflaba el MAD de S y apagaba el puntaje z. La mediana y el MAD se calculan sin las filas de tono rojo.
5. **σ̂: el gradiente para excluir bordes se mide sobre la imagen suavizada.** Medido sobre la imagen ruidosa, descarta justo los píxeles más ruidosos.
6. **Tolerancia de ancho:** no se evalúan los huecos vecinos a un bloque azul. Su borde lo define la pintura (en IMG_1001 uno medía 19,5°).
7. **Ancho incorrecto también en barras.** En el disco de "anchura incorrecta" los orificios están en tolerancia; lo que cambia son tres barras de ~25° (normal 15°). A2 se marca si un orificio o una barra queda fuera de su tolerancia de 3σ. Con esto el disco de anchura da siempre 3 espacios marcados y los demás discos ninguno.
8. **Diámetro aparente con una foto de referencia** (`escala.py`). Se reporta el tamaño aparente del disco en la foto, no el real. `datos/referencia_escala.jpg` es la foto a la distancia estándar, donde el disco mide 59,5 mm. Su diámetro en píxeles fija la escala (`px_por_mm`, 21,7 con la referencia actual), y en cada foto el diámetro aparente es D0 / px_por_mm. Si el disco está más cerca se ve más grande y si está más lejos, más pequeño: las tomas "Largo" dan 20–27 mm y las inclinadas, más cerca de la cámara, ~90 mm. Todas las longitudes se llevan a píxeles de la resolución nativa de la cámara (4752 × 3168): una imagen con la misma proporción y otro ancho se toma como reducida y se reescala; una con otra proporción se toma como recorte. La medición de la referencia se guarda en `referencia_escala.json` y se rehace sola si cambias la imagen. Para mayor precisión conviene reemplazar `referencia_escala.jpg` por el archivo original de la cámara.
9. **Línea de referencia trazada con tres puntos.** El ángulo inicial sale de la banda de la marca (0,25–0,40 R), y su puntaje decide si la marca es legible. Después se busca la línea en tres bandas, a ±5° de ese ángulo: dos en la zona blanca interior (0,15–0,24 R y 0,32–0,41 R) y una en el borde exterior, después de la corona (0,935–0,975 R). Cada punto se afina con una parábola sobre el puntaje y se usa si su puntaje es ≥ 2. Por los puntos usados se ajusta una recta (`cv2.fitLine`) que no se obliga a pasar por el centro. Con menos de dos puntos se usa el rayo radial. En las 78 fotos diagnosticables: 65 con 3 puntos y 13 con 2; el ángulo cambia en promedio 0,5° (máximo 3°) y la línea pintada queda en promedio a unos 3,5 px del centro en la foto (máximo ~11 px). La imagen de defectos y la vista polar dibujan la recta y sus puntos (blanco = usado, gris = descartado).

### Lo que muestra la interfaz

La app tiene cuatro pestañas: Resultado, Ruido, Calidad de la foto y Mediciones. Resultado muestra dos imágenes separadas: primero el disco ubicado en la foto original (borde verde, anillos de la corona en blanco, franja azul donde se cuentan los orificios), que aparece apenas se encuentra el disco, y después el disco enderezado con los defectos marcados.

La app usa nombres sencillos (por ejemplo "orificios encontrados" en vez de N, "ángulo de la línea de referencia" en vez de θ_ref, "ruido medido" en vez de σ̂). La pestaña de calidad explica qué revisa cada criterio.

Cada defecto lleva la misma etiqueta en la lista y en la imagen: S1, S2… para sectores ausentes, E1, E2… para anchos incorrectos (recuadro amarillo) y M1, M2… para manchas (recuadro rojo). Los orificios se numeran del 1 al N en sentido antihorario desde la línea de referencia.

### Para la memoria

- **σ generada vs σ̂:** σ̂ ≈ 0,11·σ, mucho menos que el 0,78 que se estimaba en el prototipo. El gris pondera los canales (×0,67), el INTER_AREA a DN promedia (×0,45) y el bilineal del `warpAffine` vuelve a promediar (×0,5). Aun así, el diagnóstico se mantiene igual que en la foto limpia hasta σ = 40 con K ≥ 3.
- **Canny vs contraste relativo** (`datos/salidas_calibracion/graficas/marca_contraste_vs_canny.csv`): coinciden (±3°) en 9/12 con luz difusa, 8/8 en oscuras, 0/12 en desenfocadas y 5/12 en luz directa con manchas. Confirma la decisión de descartar Canny.
- **Alternativas implementadas** para el estudio 6.1: `segmentacion.localizar_hough`, `caracteristicas.marca_canny`, `caracteristicas.contar_componentes` y el filtro gaussiano (opción en la app). `mediciones.csv` ya trae `theta_canny` y `N_componentes`.
- **Limitaciones:** una mancha sobre un hueco no se ve. Con sobreexposición el rojo pierde saturación. El disco de 16 huecos a ~40° pierde huecos por el espesor del acrílico.

### Pendiente

- Fotos a 15 a 20° para fijar THETA_MAX y fotos de distancia con encuadre completo.
- Fondo texturizado.
- Captura con webcam: solo cambia la fuente de la imagen en `adquisicion.py`.
