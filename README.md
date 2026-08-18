# FAW — Fabric Agentic Workflow

Un método de trabajo para agentes de IA que construyen soluciones de datos sobre Microsoft Fabric. Fases en orden, compuertas verificadas por scripts, y hooks que las hacen cumplir **fuera del modelo** — el agente no puede saltárselas por olvido, y saltárselas a propósito deja rastro.

> En software, lo que falla se rompe ruidosamente. En una plataforma de datos, el fallo típico es **un número creíble y falso**: una tabla publicada con menos columnas de las que declara, validada porque el conteo de filas daba bien; una relación que apunta a la columna equivocada y devuelve totales plausibles; una FK nula que hace desaparecer partidas al filtrar, sin ningún error. FAW existe para que detectar eso no dependa de que alguien se acuerde.

Cada regla del método cierra una vía por la que un dato incorrecto llega a producción sin hacer ruido. Ninguna está porque suene bien: si una regla no se puede atar a un modo de fallo concreto, no es una regla del método.

## Cómo funciona

Todo pedido se clasifica en un **tier**, y el tier decide cuánto proceso paga:

| Tier | Recorrido | Ejemplo |
|---|---|---|
| `CONSULTA` | Se responde y listo | "¿qué es TMDL?" |
| `EXPLORACION` | Perfilar → documento | investigar Import vs. Direct Lake |
| `CAMBIO-MENOR` | Clasificar → construir → publicar | reasignar un lakehouse a 3 notebooks |
| `ARTEFACTO` | Las seis fases | una tabla, un notebook, un pipeline |
| `MODELO` | Las seis, verificado por API | un modelo semántico |
| `REPORTE` | Brief acordado → construcción libre → publicar | un reporte Power BI |
| `INCIDENTE` | Carril rápido, diagnóstico medido | algo roto en DEV o PRD |

Las seis fases, para los tiers que las recorren:

```
CLASIFICACIÓN → PERFILADO → DISEÑO → CONSTRUCCIÓN → VALIDACIÓN → PUBLICACIÓN
     │             │           │           │             │            │
 tier, alcance,  medir el   grano, clave  skill oficial  otro agente  diff completo,
 OK del usuario  origen     natural,      de MS primero; busca        PR, sync del
                 (solo      contrato      validaciones   REFUTAR,     workspace,
                 lectura)   de datos      adentro        no confirmar tracker
```

Tres ideas sostienen todo:

1. **Evidencia antes que declaración.** Un número sin la consulta que lo produjo no es un dato: es una opinión con formato de dato. La fase PERFILADO —que un pipeline de software no tiene— existe porque en datos la mitad de los requisitos se descubren midiendo.
2. **Compuertas con recibos.** Cada verificador, al pasar, emite un recibo con el hash de lo que verificó; la máquina de estados recomputa los hashes, y un recibo vencido cierra la compuerta. Las compuertas que son solo una declaración del agente están **marcadas como tales** — una compuerta a la que se le puede mentir sin avisar convierte a las demás en sugerencias.
3. **Hooks fuera del modelo.** Instalado como plugin de Claude Code, FAW inyecta la fase actual en cada turno, deniega escrituras sin clasificación previa, revisa cada commit (metadata protegida, literales de plataforma inventados) y cada PR (checklist de superficie de cliente) **antes de que existan**.

## En dos minutos

```bash
claude plugin marketplace add DiLoretoT/faw
claude plugin install faw@faw            # carga hooks, skills y el agente validador
```

Activar en un proyecto (los hooks no hacen nada sin esto):

```bash
mkdir .faw
```

Primer uso: pedile algo al agente. Va a clasificarlo, proponerte tier y alcance, y **esperar tu OK** antes de tocar nada — si intenta escribir antes, el hook lo deniega y le explica por qué. El estado vive en `.faw/estado.jsonl` y sobrevive cerrar la sesión:

```bash
python <ruta-de-faw>/scripts/estado.py estado    # ¿dónde quedamos?
```

## Qué atrapa cada compuerta

| Verificador | Atrapa |
|---|---|
| `verificar_contrato.py` | una tabla publicada con menos columnas de las que declara |
| `verificar_modelo.py` | relaciones invertidas, storage mode o summarize equivocados |
| `verificar_diff.py` | el commit "de formato" que además borra el `default_lakehouse` |
| `verificar_plataforma.py` | un `$schema` o connection string de Microsoft **inventado por analogía** |
| `verificar_brief.py` | un reporte construido sin acordar objetivo y audiencia |
| `verificar_reporte.py` | el filtro de desarrollo olvidado y persistido en el PBIR |
| `autoverificar.py` | que los propios verificadores no se hayan roto con el tiempo |

**Los límites, sin adornos:** Livy (código Spark arbitrario), escrituras vía MCP y archivos escritos desde `Bash` no pasan por los hooks — ahí FAW detecta, no previene. Está documentado en [`GUIA_COMPLETA.md`](GUIA_COMPLETA.md) §14 en vez de prometido.

## Documentación

| Documento | Qué es |
|---|---|
| [`GUIA_COMPLETA.md`](GUIA_COMPLETA.md) | **El canónico.** Método completo, mecánica interna, ciclo con comandos reales, instalación |
| [`docs/INSTALACION.md`](docs/INSTALACION.md) | Instalación paso a paso, verificación, overrides de un solo uso |
| [`faw/reglas/`](faw/reglas/) | Lo que el agente lee: principios, fases, superficie de cliente, capa Microsoft |

## Origen

Inspirado en [dilux-agentic-workflow (DAW)](https://github.com/soydiloreto/dilux-agentic-workflow), del que toma las fases con compuertas aplicadas fuera del modelo, los tiers, la escala honesta de fuerza de las compuertas y que valide quien no construyó. Lo que cambia es el objeto: DAW verifica que el código compile y los tests pasen; FAW verifica que una tabla tenga las columnas que dice tener.

La mecánica de plataforma (cómo se escribe un notebook, qué API despliega un modelo) no vive acá a propósito: la mantiene Microsoft en [`skills-for-fabric`](https://github.com/microsoft/skills-for-fabric), y FAW la consume como capa complementaria — FAW manda en proceso, ellas en mecánica.

v2, agosto 2026. Es normativa de proceso: define qué se verifica, en qué orden y con qué evidencia. No documenta proyectos ni casos.

## Licencia

[Apache-2.0](LICENSE)
