# Experimento

Autor: Angel Salazar Lima · CIP 404730

## Pregunta

¿Un pipeline léxico y determinista (TF-IDF + cobertura) puede responder con cita correcta preguntas sobre SOPs internos y abstenerse cuando el corpus no contiene la respuesta?

## Hipótesis

| # | Hipótesis | Criterio de éxito |
|---|---|---|
| H1 | El documento correcto aparece entre los `k=4` primeros chunks | recall@4 ≥ 0.90 |
| H2 | La respuesta cita el documento esperado y contiene los datos clave | citation hit ≥ 0.90, keyword score ≥ 0.50 por caso |
| H3 | Ante preguntas sin evidencia, el sistema se abstiene | abstención correcta = 100 %, falsa respuesta = 0 % |
| H4 | Umbral de cobertura 0.45 equilibra respuestas y abstenciones | sin falsas abstenciones en el gold set |

## Diseño

- **Corpus:** 4 documentos en `samples/docs/` (reembolsos, accesos, incidentes, vacaciones y trabajo remoto) → 32 chunks, 389 términos.
- **Gold set:** `samples/gold/questions.jsonl` con 13 casos: 11 respondibles (3 reembolsos, 3 accesos, 2 incidentes, 3 vacaciones/remoto) y 2 sin evidencia (precio del bitcoin, mundial 2018).
- **Un caso pasa si:** la abstención coincide con la esperada, el documento esperado está en el top-k, aparece en las citas y al menos 50 % de las palabras clave esperadas están en la respuesta.
- **Reproducción:**

```bash
python -m knowledge_ops ingest samples/docs
python -m knowledge_ops eval
```

La ejecución es determinista: el mismo corpus y gold set producen las mismas métricas. El snapshot se versiona en [`results/eval.md`](../results/eval.md) y [`results/eval.json`](../results/eval.json).

## Resultados

Corrida con `k=4`, umbrales por defecto (`MIN_COVERAGE=0.45`, `MIN_CONFIDENCE=0.40`):

| Métrica | Valor |
|---|---|
| Casos | 13 (11 respondibles, 2 sin evidencia) |
| recall@4 | 100 % |
| citation hit | 100 % |
| keyword score | 100 % |
| abstención correcta | 100 % |
| falsa abstención | 0 % |
| falsa respuesta | 0 % |
| pass rate | 100 % (13/13) |

Confianza en casos respondidos: mínimo 0.55 (q07, incidente severidad 1), máximo 1.00 (q11, bono de internet). Confianza en los dos casos sin evidencia: 0.00.

### Sensibilidad a `k`

| k | recall@k | citation hit | pass rate |
|---|---|---|---|
| 1 | 100 % | 100 % | 100 % |
| 2 | 100 % | 100 % | 100 % |
| 4 | 100 % | 100 % | 100 % |
| 8 | 100 % | 100 % | 100 % |

### Sensibilidad al umbral de cobertura (k=4, confianza mínima 0.40)

| `min_coverage` | citation hit | abstención correcta | falsa abstención | pass rate |
|---|---|---|---|---|
| 0.30 | 100 % | 100 % | 0 % | 100 % |
| 0.45 | 100 % | 100 % | 0 % | 100 % |
| 0.60 | 72.7 % | 76.9 % | 27.3 % | 76.9 % |
| 0.75 | 36.4 % | 46.2 % | 63.6 % | 46.2 % |

### Sondeo adversarial fuera del gold

Seis preguntas redactadas con vocabulario del dominio pero sin respuesta en el corpus, ejecutadas a mano con `answer_question`:

| Umbral | Preguntas que se abstienen |
|---|---|
| `min_coverage=0.45` (por defecto) | 6 de 6 (coberturas observadas 0.22–0.37) |
| `min_coverage=0.30` | 3 de 6 |

Con 0.30 respondieron "política de reembolso de Amazon", "vacaciones del presidente" y "trabajar remoto desde otro país", citando contenido que no responde la pregunta.

## Lectura de hipótesis

- **H1, H2, H3, H4: se cumplen** en el gold set actual.
- **El gold set no discrimina por sí solo el umbral:** 0.30 y 0.45 dan 100 % porque solo hay 2 casos de abstención y ambos son totalmente ajenos al dominio. La elección de 0.45 la respalda el sondeo adversarial, no el gold.
- **Umbrales altos dañan el recall útil:** desde 0.60 aparecen falsas abstenciones en preguntas legítimas.

## Amenazas a la validez

- Corpus de 4 documentos sintéticos escritos para el ejercicio; las preguntas comparten vocabulario con ellos. 100 % no se debe extrapolar a corpus reales.
- Gold set pequeño (13 casos, 2 de abstención): un solo fallo mueve el pass rate ≈ 7.7 puntos.
- El sondeo adversarial son 6 preguntas manuales, no un conjunto versionado.
- Las palabras clave son coincidencias de subcadena sin acentos: no validan que la respuesta sea semánticamente correcta.
- Las preguntas parafraseadas con sinónimos no están cubiertas.
