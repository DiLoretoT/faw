---
name: faw-validar
description: Fase de validación de FAW. Lanza el agente faw-validador para que un agente que NO construyó verifique el artefacto contra su contrato y contra la realidad medida.
---

# Validar

Fase 5 de FAW. **La ejecuta un agente distinto del que construyó.**

## Por qué se delega y no lo hacés vos

Si construiste esto, ya decidiste que está bien. Al validarlo vas a buscar confirmación en vez de refutación — no por descuido, por cómo funciona revisar el propio trabajo.

Un conteo de filas correcto no prueba nada por sí solo: una dimensión puede coincidir exactamente con las filas esperadas y aun así tener menos de la mitad de sus columnas. El conteo estaba bien y una revisión que solo lo mira a él la habría dado por buena igual.

Por eso esta fase se delega, siempre, aunque parezca trámite.

## Cómo

Lanzá el agente `faw-validador` con el contrato, el recibo de perfilado y el diseño. **No le pases tu razonamiento de construcción** — si el artefacto necesita que se lo expliquen, está mal documentado.

```
Agent(subagent_type="faw-validador", prompt="
Validá <artefacto> en <ambiente>.
Contrato:  contratos/<esquema>.<tabla>.yml
Perfilado: docs/faw/<ticket>/perfilado.md
Diseño:    docs/faw/<ticket>/diseno.md
Escribí el veredicto en docs/faw/<ticket>/validacion.md
")
```

## Qué tiene que devolver

Veredicto **PASA** o **FALLA**, con:

1. Esquema contra contrato, columna por columna (`verificar_contrato.py`).
2. Números del artefacto contra los del perfilado, con las diferencias explicadas por filtros declarados.
3. Reglas de calidad del contrato, corridas.
4. Modelo semántico verificado por API, si aplica (`verificar_modelo.py`).
5. Hallazgos abiertos con su impacto.
6. Qué quedó fuera de su alcance — típicamente la corrección de negocio, con quién debería confirmarla.

Un "pasa pero" es un falla con mala redacción. Tratalo como falla.

## Si falla

Volvés a CONSTRUCCIÓN:

```bash
python <faw>/scripts/estado.py mover --a CONSTRUCCION
```

**No parchees en validación.** El parche lo escribiría el validador y ya no queda nadie mirando desde afuera.

## Si pasa

```bash
python <faw>/scripts/estado.py mover --a PUBLICACION --compuerta esquema="ok: 20 columnas, coinciden con el contrato"
```

Para tier `MODELO`, además `--compuerta modelo="ok: ..."` y `--compuerta reconciliacion="..."`.
