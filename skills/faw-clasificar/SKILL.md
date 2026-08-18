---
name: faw-clasificar
description: Arranca un trabajo bajo FAW. Clasifica el pedido, asigna tier, define alcance y abre el estado. Usar al empezar cualquier trabajo de datos sobre Fabric.
---

# Clasificar

Fase 1 de FAW. **No construyas nada todavía.**

## Qué hacés

1. **Reformulá el pedido en una frase.** Si la reformulación no te sale obvia, preguntá antes de seguir.

2. **Mirá el estado real**, no lo que suponés:
   - `python scripts/estado.py estado`
   - `git status --porcelain` y rama actual
   - los artefactos que el pedido toca — ¿existen?, ¿tienen contrato?

3. **Asigná tier y justificalo en una línea:**

   | Tier | Cuándo |
   |---|---|
   | `CONSULTA` | Una pregunta. Sin rama ni artefactos. |
   | `EXPLORACION` | Entender algo sin tocarlo. Prohibido escribir en el tenant. |
   | `CAMBIO-MENOR` | Ajuste acotado, sin tocar esquema ni lógica de negocio ni capa de consumo, ~30 líneas. |
   | `ARTEFACTO` | Tabla, notebook o pipeline nuevo o modificado. |
   | `MODELO` | Modelo semántico: tablas, relaciones, medidas, storage mode. |
   | `REPORTE` | Reporte Power BI. **Exige brief acordado con el usuario antes de construir** (ver abajo). |
   | `INCIDENTE` | Algo roto en DEV o PRD. |

   Ante la duda entre `CAMBIO-MENOR` y `ARTEFACTO`, es `ARTEFACTO`.

   `MODELO` y `REPORTE` eran un solo tier (`SEMANTICO`) y se separaron: el rigor de compuertas
   fuertes responde a errores de **modelo** — relaciones, storage mode, propiedades —, no de
   reporte. Cobrarle al reporte el rigor del modelo era un error de calibración.

6. **Si el tier es `REPORTE`, la clasificación incluye el brief.** No se entra a construir sin haber
   acordado **con el usuario** para qué existe el reporte: objetivo, audiencia, las preguntas que
   tiene que responder, qué no entra, origen de datos y quién valida los números. Se llena en
   `docs/faw/<ticket>/brief.md` a partir de `faw/contratos/PLANTILLA.brief.md`, y lo verifica
   `scripts/verificar_brief.py`, que rechaza el template sin llenar. Deducir el alcance leyendo el
   modelo semántico **no es clasificar**: es construir el brief solo, sin la conversación que lo
   valida. La mecánica de esa conversación la cubre la skill oficial `powerbi-report-planning`:
   leerla antes.

4. **Definí alcance: qué entra y qué NO.** La segunda parte importa más — es lo que evita que el trabajo crezca solo.

5. **Rama** `<tipo>/<slug>` si el tier la necesita.

## Cierre

Presentá al usuario, corto:

```
Pedido    : <una frase>
Tier      : <tier> — <justificación en una línea>
Entra     : <lista>
No entra  : <lista>
Rama      : <nombre>
Próximo   : <fase siguiente> — <acción concreta que vas a hacer ahí, no solo el nombre>
```

**"Próximo" dice qué acción sigue, no solo a qué fase se mueve** (principio 14). "Próximo: PERFILADO" no alcanza; "Próximo: PERFILADO — voy a correr count(*) vs count(distinct) sobre la clave candidata y medir nulos por columna" sí.

**Esperá confirmación.** Es la única compuerta puramente humana del método, y es a propósito: acá se decide cuánto proceso va a costar todo lo demás.

Con el OK:

```bash
python scripts/estado.py iniciar --ticket <T> --tier <TIER> --titulo "<t>"
```

## Trampas

- **No arranques a construir mientras clasificás.** Es la desviación más común y la que hace que el resto del método no se aplique.
- Si el pedido son varias cosas, clasificalas por separado. Un trabajo, un ticket.
- Si al clasificar como `CONSULTA` te das cuenta de que hay que tocar algo, reclasificá **antes** de tocarlo.
