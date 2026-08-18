---
name: faw-backlog
description: Trae el backlog de Azure DevOps, muestra en qué estado está el sprint y propone con qué seguir. También reconcilia un pedido fuera de backlog contra las User Stories existentes. Usar al empezar una jornada o cuando no está claro qué sigue.
---

# Backlog

Puente entre el backlog de Azure DevOps y FAW. Responde dos preguntas: **¿con qué sigo?** y **¿esto que me están pidiendo dónde encaja?**

## Antes que nada: cómo leer ADO

**El MCP de ADO (`mcp__ado__*`) no siempre ve todos los proyectos** — hay al menos un proyecto donde falla y no es un problema de permisos. Si `mcp__ado__core_list_projects` no lo lista, **no insistas ni asumas que no hay acceso**: usá la CLI, que sí funciona.

```bash
# Iteración actual y sus work items
az boards iteration project list --project "<proyecto>" --org https://dev.azure.com/<org>

# Query por WIQL: lo abierto del sprint actual
az boards query --org https://dev.azure.com/<org> --project "<proyecto>" \
  --wiql "SELECT [System.Id],[System.Title],[System.State],[System.WorkItemType],[Microsoft.VSTS.Scheduling.StoryPoints] FROM WorkItems WHERE [System.IterationPath] = @currentIteration AND [System.State] <> 'Closed' ORDER BY [System.WorkItemType], [System.Id]"

# Un work item concreto
az boards work-item show --id <id> --org https://dev.azure.com/<org>
```

Los IDs numéricos son la referencia canónica (`#1000`), no los títulos ni alias.

## Qué hacés — modo "con qué sigo"

1. **Traé el estado real del sprint.** No de memoria ni del roadmap: de ADO.

2. **Armá el panorama, corto:**

   ```
   Iteración : <nombre>  ·  <N> ítems abiertos  ·  <SP> SP restantes
   En curso  : #id título (estado)
   Bloqueado : #id título — por qué
   Siguiente : #id título (SP)  ← propuesta
   ```

3. **Proponé el siguiente con criterio, no el primero de la lista.** El orden importa y lo decide:
   - **Dependencias técnicas** primero. Las dimensiones antes que los hechos, siempre. Si una US necesita algo que no está construido, no es candidata aunque esté arriba.
   - **Lo bloqueado no se propone**, se reporta como bloqueado y con qué se desbloquea.
   - **Lo que desbloquea a otros** vale más que lo que no.
   - Si dos son equivalentes, la de menos Story Points: cerrar cosas mueve más que empezarlas.

4. **Cruzá con el estado de FAW.** Si `estado.py estado` muestra trabajo abierto, decilo antes de proponer nada nuevo.

5. **Al proponer el siguiente, decí en una frase qué vas a hacer si el usuario confirma** (principio 14) — no alcanza con "¿arrancamos con #1001?". Ej.: "¿Arrancamos con #1001 — voy a revisar el estado real del origen antes de proponer diseño?".

6. **Al elegir, pasás a CLASIFICACIÓN** con el ID de la US como ticket:
   ```bash
   python scripts/estado.py iniciar --ticket 1001 --tier ARTEFACTO --titulo "<título de la US>"
   ```

## Qué hacés — modo "esto encaja en el backlog?"

Cuando el pedido viene por fuera (chat, mail, una reunión):

1. **Buscá si ya existe** una US que lo cubra. Si existe, se trabaja contra esa: no se duplica.
2. Si no existe, clasificá:

   | El pedido es… | Qué hacés |
   |---|---|
   | Parte del alcance de una US existente | Se trabaja en esa US. Comentario en ADO si aporta contexto. |
   | Trabajo nuevo dentro del alcance del proyecto | **Proponés crear la US** con título, criterios de aceptación y SP estimados. No la creás sin OK. |
   | Fuera del alcance contratado | **Lo decís.** Puede necesitar conversación comercial antes que técnica. |
   | Un incidente | Tier `INCIDENTE`. La US se crea después, documentando qué pasó. |

3. **Nunca creás ni cerrás work items sin OK explícito.** Proponés el texto y esperás.

## Nomenclatura

Sin prefijos de orden en los títulos (`A1 ·`, `E1 ·`). El título es solo el contenido; el orden sale de la jerarquía y los tags.

## Qué producís

Nada en disco. El panorama va en el chat, y el resultado es un CLASIFICACIÓN arrancado o una propuesta de US para que apruebes.

## Trampas

- **Proponer trabajo que ya está hecho** porque el backlog no se actualizó. Si el estado de ADO no coincide con lo que ves en Fabric, decilo — probablemente haya que cerrar ítems.
- **Tomar el orden del backlog como orden de ejecución.** El backlog está priorizado por valor; la ejecución la ordenan las dependencias técnicas.
- **Crear una US para cada pedido chico.** Un ajuste de `CAMBIO-MENOR` no necesita US propia si cae dentro de una existente.
