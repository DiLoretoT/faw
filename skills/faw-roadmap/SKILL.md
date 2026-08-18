---
name: faw-roadmap
description: Revisa el roadmap y el backlog contra cómo viene realmente el proyecto, y propone reencauzarlo. Usar al cierre de un sprint, cuando aparece información del cliente que cambia supuestos, o cuando algo técnico salió distinto de lo previsto.
---

# Revisión de roadmap

Un backlog se escribe con la información que había el primer día. Dos meses después, parte de esa información es falsa: el cliente dijo algo nuevo, una tabla no tenía la clave que se suponía, una feature de la plataforma no hace lo que prometía. Esta revisión existe para que el backlog vuelva a describir la realidad.

**No es una actualización de estado.** Es preguntarse si el plan sigue siendo el plan correcto.

## Cuándo corresponde

- Al cerrar un sprint.
- Cuando aparece información del cliente que cambia un supuesto.
- Cuando algo técnico salió distinto de lo previsto y afecta más de una US.
- Cuando llevás varias sesiones sintiendo que el backlog no refleja lo que estás haciendo.

## Qué hacés

### 1. Traer los tres estados, sin mezclarlos

| Fuente | Qué dice |
|---|---|
| **ADO** | Qué se planificó y en qué estado figura |
| **El roadmap / tracker interno** | Qué se decidió, qué quedó pendiente, qué preguntas están abiertas |
| **Fabric y el repo** | Qué existe **de verdad** — tablas, notebooks, modelos |

Traelos por separado. **Las discrepancias entre los tres son el material de esta revisión**, no un problema a ocultar.

### 2. Encontrar los desvíos

Buscá específicamente, y con nombre y apellido:

| Tipo de desvío | Cómo se detecta |
|---|---|
| **Hecho pero no cerrado** | Existe en Fabric, la US sigue abierta |
| **Cerrado pero no hecho** | La US está Closed, el artefacto no existe o está incompleto |
| **Hecho y no planificado** | Trabajo real que no tiene US — deuda de registro |
| **Planificado y ya sin sentido** | Una US cuyo supuesto se cayó |
| **Bloqueado hace tiempo** | Sin movimiento y sin dueño de desbloqueo |
| **Alcance que creció en silencio** | Lo entregado es más de lo que la US pedía |
| **Dependencia nueva** | Algo que ahora requiere otra cosa antes, y el orden del backlog no lo refleja |

### 3. Rastrear la causa

Por cada desvío, **qué información nueva lo produjo**. Es lo que distingue reencauzar de improvisar:

- **Información del cliente** — dijeron algo que cambia el alcance o la definición.
- **Realidad técnica** — la plataforma o el origen no se comportan como se suponía.
- **Estimación equivocada** — el trabajo era más grande o más chico.
- **Descubrimiento** — apareció trabajo necesario que nadie había visto.

Un desvío sin causa identificada suele significar que falta información, no que no haya causa.

### 4. Proponer los cambios

Concreto y accionable, agrupado por tipo de acción:

```markdown
## Cerrar
- #1001 — está construido y validado desde el <fecha>.

## Reabrir o corregir
- #1002 — figura Closed pero <qué falta>.

## Crear
- <título> — <por qué apareció>. SP estimados: N.
  Criterios de aceptación: ...

## Reordenar
- #1004 tiene que ir antes de #1003: <dependencia>.

## Repriorizar o sacar del sprint
- #1005 — el supuesto se cayó porque <causa>. Propongo <acción>.

## Reestimar
- #1006 — de N a M SP porque <causa>.
```

### 5. Lo que hay que llevar al cliente

Separado del resto, porque no es trabajo técnico y no lo decidís vos:

- Preguntas abiertas que **bloquean** trabajo planificado, con qué se bloquea.
- Cambios de alcance que requieren conversación antes de ejecutarse.
- Decisiones que esperan a alguien del negocio, con nombre.

## Qué producís

1. **En el chat:** el resumen de desvíos y las propuestas.
2. **Con tu OK:** actualización del tracker interno con la revisión fechada.
3. **Con tu OK, por separado:** los cambios en ADO. **Nunca toco work items sin autorización explícita** — cerrar una US ajena o repriorizar un sprint tiene consecuencias fuera de lo técnico.

## Trampas

- **Confundir esto con reportar avance.** Si el resultado es "vamos al 40%", no hiciste una revisión de roadmap. La pregunta es si el 60% restante sigue siendo el correcto.
- **Cerrar ítems por optimismo.** Una US se cierra cuando el artefacto existe y está validado, no cuando "está casi".
- **Ocultar el trabajo no planificado.** Es la información más valiosa de la revisión: dice dónde el plan original no vio algo.
- **Proponer reencauzar todo.** Si la revisión propone cambiar quince ítems, probablemente el problema sea otro y haya que hablarlo antes de tocar el backlog.
