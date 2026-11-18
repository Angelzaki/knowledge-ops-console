# Evaluación del gold set

Gold: `samples/gold/questions.jsonl` · k=4 · casos=13

| Métrica | Valor |
|---|---|
| recall@4 | 100.00% |
| citation hit | 100.00% |
| keyword score | 100.00% |
| abstención correcta | 100.00% |
| falsa abstención | 0.00% |
| falsa respuesta | 0.00% |
| pass rate | 100.00% |

## Casos

| ID | Resultado | Abstuvo | Confianza | Doc esperado | Docs citados |
|---|---|---|---|---|---|
| q01 | OK | no | 0.70 | sop_reembolsos.txt | sop_reembolsos.txt |
| q02 | OK | no | 0.90 | sop_reembolsos.txt | sop_reembolsos.txt |
| q03 | OK | no | 0.91 | sop_reembolsos.txt | sop_reembolsos.txt |
| q04 | OK | no | 0.73 | politica_accesos.txt | politica_accesos.txt |
| q05 | OK | no | 0.84 | politica_accesos.txt | politica_accesos.txt |
| q06 | OK | no | 0.71 | politica_accesos.txt | politica_accesos.txt |
| q07 | OK | no | 0.55 | sop_incidentes.txt | sop_incidentes.txt |
| q08 | OK | no | 0.64 | sop_incidentes.txt | sop_incidentes.txt |
| q09 | OK | no | 0.79 | politica_vacaciones_remoto.txt | politica_vacaciones_remoto.txt |
| q10 | OK | no | 0.82 | politica_vacaciones_remoto.txt | politica_vacaciones_remoto.txt |
| q11 | OK | no | 1.00 | politica_vacaciones_remoto.txt | politica_vacaciones_remoto.txt |
| q12 | OK | sí | 0.00 | — | — |
| q13 | OK | sí | 0.00 | — | — |
