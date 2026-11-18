# Conclusiones

Autor: Angel Salazar Lima · CIP 404730

Datos y método en [EXPERIMENT.md](EXPERIMENT.md).

## Qué se demostró

1. **El pipeline funciona de extremo a extremo en el corpus de ejemplo.** 13/13 casos del gold set pasan: recall@4, citation hit y abstención correcta en 100 %, con 0 % de falsas respuestas y 0 % de falsas abstenciones.
2. **Cada respuesta es auditable.** El texto es extractivo y lleva cita `[n]` a documento, sección y fragmento; las abstenciones registran el motivo (`cobertura baja`, `confianza baja`, `sin coincidencias léxicas`).
3. **La abstención es una decisión medible.** La cobertura ponderada por idf separa bien el dominio del ruido: las preguntas fuera del corpus quedaron en 0.22–0.37 y las respondibles superan el umbral de 0.45.

## Qué no se demostró

- **Generalización.** Corpus de 4 documentos y 13 preguntas. El 100 % mide que el sistema no está roto, no que sea suficiente para producción.
- **Robustez ante paráfrasis.** La recuperación es léxica; sinónimos y reformulaciones lejanas pueden caer bajo el umbral y producir abstenciones innecesarias.
- **Calidad semántica de la respuesta.** El criterio de palabras clave detecta datos faltantes, no contradicciones.

## Hallazgo principal

El gold set, tal como está, no distingue entre un umbral de cobertura de 0.30 y uno de 0.45. Solo el sondeo adversarial mostró que 0.30 deja pasar 3 de 6 preguntas engañosas con respuestas citadas que no corresponden. Un sistema que cita con aparente rigor una fuente irrelevante es peor que uno que se abstiene.

## Decisiones

| Decisión | Motivo |
|---|---|
| Mantener `MIN_COVERAGE=0.45` y `MIN_CONFIDENCE=0.40` | Máxima cobertura sin falsas abstenciones en el gold y 6/6 en el sondeo |
| No subir el umbral a 0.60 o más | Falsas abstenciones de 27 % a 64 % en preguntas legítimas |
| Priorizar abstención sobre respuesta | Una respuesta citada pero incorrecta tiene mayor costo que escalar a una persona |
| Gate de CI sobre `pass_rate` | Un cambio de tokenizador o umbral que degrade el gold falla antes de integrarse |

## Siguientes pasos

1. Ampliar el gold set a 50 o más casos, con al menos 15 de abstención y preguntas cercanas al dominio (no solo ajenas).
2. Versionar el sondeo adversarial como segundo archivo gold.
3. Añadir casos parafraseados para medir el techo de la recuperación léxica antes de considerar embeddings.
4. Si la paráfrasis degrada recall, comparar contra una recuperación densa usando [rag-eval-platform](https://github.com/Angelzaki/rag-eval-platform) como banco de pruebas.
5. Filtrar consultas hostiles antes de `ask` con [prompt-firewall](https://github.com/Angelzaki/prompt-firewall).
