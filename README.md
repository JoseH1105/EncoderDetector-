# Diagnóstico de un codificador óptico (v1.4)

Sistema de visión que revisa un disco codificador a partir de una foto: lo localiza, comprueba que la imagen sea legible, cuenta los huecos, encuentra la marca azul de referencia y detecta sectores ausentes, anchos incorrectos, sectores añadidos y manchas rojas. Implementa la especificación `solucion_diagnostico_encoder_v1.4.md`.

## Instalación

En tu entorno de miniconda:

```bash
conda activate <tu_entorno>
pip install opencv-python numpy "gradio>=5" matplotlib pandas
```

Probado con Python 3.13, OpenCV 5.0 y Gradio 6.29. El código también funciona con Gradio 5.

## Uso rápido

Desde la carpeta del proyecto:

```bash
python app_diagnostico.py         # app del sistema      
python app_generador_ruido.py     # generador de ruido   
```

En la app sube una foto JPG o PNG y pulsa **Diagnosticar**. Las pestañas se llenan etapa por etapa. Si la imagen no pasa la validación, el proceso se detiene en esa pestaña y muestra el motivo. Si existe la carpeta `Fotos T2` junto a la carpeta del proyecto, la app ofrece una foto de ejemplo por condición.

## Estructura

```
encoder_diag/
├── app_diagnostico.py          # app del sistema (puerto 7860)
├── app_generador_ruido.py      # app aparte del generador de ruido (puerto 7861)
├── calibrar.py                 # medición por lotes y reglas de umbral
├── requirements.txt
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

Las apps y `calibrar.py` se ejecutan desde la raíz del proyecto; los módulos de `subfunciones/` no se ejecutan solos. La carpeta de fotos `Fotos T2` va al lado de la carpeta del proyecto (es la ruta por defecto, `DIR_FOTOS` en `config.py`).

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

## Calibración

```bash
python calibrar.py todo --fotos "../Fotos T2"              # etiquetas + medir + umbrales + revisar
python calibrar.py ruido --zip ruido_diseno_AAAAMMDD.zip   # barrido de K_BILATERAL
python calibrar.py color                                   # opcional: muestras con cv2.selectROI
```

Las salidas quedan en `datos/salidas_calibracion/` y los umbrales en `datos/calibracion.json`.

| Paso | Salida |
|---|---|
| `etiquetas` | `etiquetas.csv`: condición (subcarpeta), conjunto diseño/prueba (el 3.er disparo de cada trío va a prueba), criterio que debería fallar y tipo de disco |
| `medir` | `mediciones.csv`: todas las métricas de los bloques 1 a 6, sin decidir |
| `umbrales` | `datos/calibracion.json`: valores y la regla que produjo cada uno |
| `revisar` | `resultados.csv` y `graficas/` (una gráfica por métrica con su umbral) |
| `ruido` | `ruido_barrido.csv` y `K_BILATERAL` en `calibracion.json` |

**Revisa la columna `disco` de `etiquetas.csv`.** El script la llena con una sugerencia a partir de k\* y N_azul (`disco_origen = sugerido`). Mientras no la corrijas a mano, los aciertos del eje A en `revisar` son en parte circulares. Si cambias una etiqueta, vuelve a correr `umbrales` y `revisar`.

Reglas usadas: si dos grupos no se traslapan, el umbral es el punto medio entre sus extremos. Si se traslapan, se toma el umbral con menos errores y, entre empates, el centro del hueco más ancho. σ_cámara es el percentil 95 de σ̂ más 0,5. La tolerancia de ancho es 3σ de los huecos del disco correcto. Los niveles de lectura usan terciles.

## Calibración v0 entregada (137 fotos, 93 de diseño)

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

## Decisiones tomadas al implementar

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

## Lo que muestra la interfaz

La app tiene cuatro pestañas: Resultado, Ruido, Calidad de la foto y Mediciones. Resultado muestra dos imágenes separadas: primero el disco ubicado en la foto original (borde verde, anillos de la corona en blanco, franja azul donde se cuentan los orificios), que aparece apenas se encuentra el disco, y después el disco enderezado con los defectos marcados.

La app usa nombres sencillos (por ejemplo "orificios encontrados" en vez de N, "ángulo de la línea de referencia" en vez de θ_ref, "ruido medido" en vez de σ̂). La pestaña de calidad explica qué revisa cada criterio.

Cada defecto lleva la misma etiqueta en la lista y en la imagen: S1, S2… para sectores ausentes, E1, E2… para anchos incorrectos (recuadro amarillo) y M1, M2… para manchas (recuadro rojo). Los orificios se numeran del 1 al N en sentido antihorario desde la línea de referencia.

## Para la memoria

- **σ generada vs σ̂:** σ̂ ≈ 0,11·σ, mucho menos que el 0,78 que se estimaba en el prototipo. El gris pondera los canales (×0,67), el INTER_AREA a DN promedia (×0,45) y el bilineal del `warpAffine` vuelve a promediar (×0,5). Aun así, el diagnóstico se mantiene igual que en la foto limpia hasta σ = 40 con K ≥ 3.
- **Canny vs contraste relativo** (`datos/salidas_calibracion/graficas/marca_contraste_vs_canny.csv`): coinciden (±3°) en 9/12 con luz difusa, 8/8 en oscuras, 0/12 en desenfocadas y 5/12 en luz directa con manchas. Confirma la decisión de descartar Canny.
- **Alternativas implementadas** para el estudio 6.1: `segmentacion.localizar_hough`, `caracteristicas.marca_canny`, `caracteristicas.contar_componentes` y el filtro gaussiano (opción en la app). `mediciones.csv` ya trae `theta_canny` y `N_componentes`.
- **Limitaciones:** una mancha sobre un hueco no se ve. Con sobreexposición el rojo pierde saturación. El disco de 16 huecos a ~40° pierde huecos por el espesor del acrílico.

## Pendiente

- Fotos a 15 a 20° para fijar THETA_MAX y fotos de distancia con encuadre completo.
- Fondo texturizado.
- Captura con webcam: solo cambia la fuente de la imagen en `adquisicion.py`.
