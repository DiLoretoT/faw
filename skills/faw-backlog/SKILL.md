---
name: faw-backlog
description: Responde con qué seguir y dónde encaja un pedido nuevo, contra el gestor de tickets que use el proyecto o contra el registro interno de FAW. Usar al empezar una jornada o cuando no está claro qué sigue.
---

# Backlog

Dos preguntas: **¿con qué sigo?** y **¿esto que me están pidiendo dónde encaja?**

## De dónde salen los tickets

Lo declara `faw.json` en la raíz del repo, bajo `tickets.sistema`. Si el archivo no existe, el valor es `interno`.

| Sistema | Dónde se leen | Cómo se opera |
|---|---|---|
| `interno` | `docs/faw/tickets/*.md` del propio repo | Se leen y se editan como archivos; el historial lo da git |
| `ado`, `jira`, `github` | El gestor declarado | Con su servidor MCP si está conectado en la sesión; si no, el usuario opera la herramienta y acá se trabaja con lo que él informe |
| `ninguno` | No hay backlog | Se trabaja sobre lo que el usuario pida en el momento |

**Antes de consultar un gestor externo, verificar si hay un servidor MCP disponible para él.** Con MCP se consulta y se actualiza directamente. Sin MCP, no se inventa el estado del backlog ni se asume que un ticket existe: se le pregunta al usuario, o se trabaja con el identificador que él dé.

Una herramienta que no tiene MCP no impide usar FAW. Lo único que el método necesita de un ticket es su identificador.

## Modo "con qué sigo"

1. **Traer el estado real.** Del gestor declarado o del registro interno, no de memoria ni de lo que se conversó la sesión pasada.

2. **Armar el panorama, corto:**

   ```
   Abiertos   : <N>
   En curso   : <id> <título>
   Bloqueado  : <id> <título> — por qué
   Siguiente  : <id> <título>   <- propuesta
   ```

3. **Proponer el siguiente ordenando por dependencia técnica, no por el orden del backlog.** Las dimensiones antes que los hechos, siempre; una tabla antes que el modelo que la consume; el modelo antes que el reporte. Lo bloqueado no se propone: se reporta como bloqueado y con qué se desbloquea.

4. **Cruzar con el estado de FAW.** Si `estado.py estado` muestra trabajo abierto, decirlo antes de proponer nada nuevo. Abrir un segundo trabajo sin cerrar el primero es cómo se pierde el hilo.

5. **Al proponer, decir en una frase qué se va a hacer si el usuario confirma** (principio 14). No alcanza con "¿arrancamos con el 1001?".

6. **Si no hay nada en el backlog**, decirlo en vez de inventar trabajo. Es el momento de ofrecer `/faw-roadmap`: un backlog vacío casi nunca significa que no haya nada que hacer, significa que nadie decidió qué sigue.

## Modo "dónde encaja esto"

Un pedido que llega por chat se reconcilia contra lo que ya existe **antes** de crear nada nuevo:

| Situación | Qué se hace |
|---|---|
| Es parte del alcance de un ticket existente | Se trabaja en ese ticket |
| Es trabajo nuevo | Se propone crear el ticket, con su alcance en una frase |
| Es una consulta que no toca nada | Se responde; no se abre ticket |
| Contradice algo ya decidido | Se dice explícitamente antes de hacerlo |

**Nunca se crea ni se cierra un ticket sin el OK del usuario**, ni en el gestor externo ni en el registro interno. Un ticket creado por iniciativa propia ensucia el backlog de alguien que no lo pidió.

## Cómo se abre el trabajo

Con el identificador que corresponda al sistema declarado:

```bash
# Gestor externo: el identificador sale de ahí
python <faw>/scripts/estado.py iniciar --ticket 1001 --tier ARTEFACTO --titulo "<título>"

# Registro interno: FAW genera el identificador y crea el archivo del ticket
python <faw>/scripts/estado.py iniciar --tier ARTEFACTO --titulo "<título>"
```

El parámetro `--artefacto` declara qué se va a construir (`notebook`, `modelo-semantico`, `reporte`, `pipeline`, `tabla`). Sirve para saber qué skill oficial de la plataforma aplica, así que conviene pasarlo siempre que se sepa.
