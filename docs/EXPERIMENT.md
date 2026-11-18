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
python -m knowledge_ops eval --all
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

### Set adversarial versionado

Las seis preguntas del sondeo manual ahora están en [`samples/gold/adversarial.jsonl`](../samples/gold/adversarial.jsonl): vocabulario del dominio, sin respuesta en el corpus, todas con `should_abstain`. Se evalúa aparte del gold principal:

```bash
python -m knowledge_ops eval --all     # principal + adversarial, reportes separados
python -m knowledge_ops eval --gold samples/gold/adversarial.jsonl
```

Reportes: [`results/eval.md`](../results/eval.md) (principal, sin cambios: 13/13) y [`results/eval_adversarial.md`](../results/eval_adversarial.md).

Con `min_coverage=0.45` (por defecto), `k=4`:

| Métrica | Valor |
|---|---|
| Casos | 6 (6 sin evidencia) |
| abstención correcta | 100 % (6/6) |
| falsa respuesta | 0 % |
| pass rate | 100 % (6/6) |
| coberturas observadas | 0.22–0.37 (todas bajo 0.45) |

Con `min_coverage=0.30` el mismo set se abstiene 3 de 6 (pass rate 50 %): responden a01 (Amazon), a02 (vacaciones del presidente) y a06 (trabajo remoto desde otro país), citando contenido que no responde la pregunta. El gold principal da 100 % en ambos umbrales, así que solo el set adversarial discrimina. Los tests cubren ambos casos (`test_adversarial_gold_*`).

## Lectura de hipótesis

- **H1, H2, H3, H4: se cumplen** en el gold set actual.
- **El gold set no discrimina por sí solo el umbral:** 0.30 y 0.45 dan 100 % porque solo hay 2 casos de abstención y ambos son totalmente ajenos al dominio. La elección de 0.45 la respalda el set adversarial (6/6 frente a 3/6 con 0.30), no el gold principal.
- **Umbrales altos dañan el recall útil:** desde 0.60 aparecen falsas abstenciones en preguntas legítimas.

## Amenazas a la validez

- Corpus de 4 documentos sintéticos escritos para el ejercicio; las preguntas comparten vocabulario con ellos. 100 % no se debe extrapolar a corpus reales.
- Gold set pequeño (13 casos, 2 de abstención): un solo fallo mueve el pass rate ≈ 7.7 puntos.
- El set adversarial es versionado pero pequeño (6 preguntas, escritas por el mismo autor que el umbral): un fallo mueve el pass rate ≈ 16.7 puntos y no mide preguntas parafraseadas.
- Las palabras clave son coincidencias de subcadena sin acentos: no validan que la respuesta sea semánticamente correcta.
- Las preguntas parafraseadas con sinónimos no están cubiertas.
