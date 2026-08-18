---
name: faw-arquitectura
description: Revisión de arquitectura de lo que se está construyendo, contrastando las decisiones tomadas contra documentación oficial de Microsoft, foros y artículos de la comunidad. Usar al cerrar una etapa, antes de replicar un patrón a otro dominio, o cuando una decisión empieza a doler.
---

# Revisión de arquitectura

Contrasta lo que estamos construyendo contra lo que la plataforma realmente soporta y lo que el resto de la industria hace. **No es un code review** — no mira si el código está bien escrito, mira si las decisiones son las correctas.

## Cuándo corresponde

- Al cerrar una etapa, antes de que la decisión se vuelva costosa de cambiar.
- **Antes de replicar un patrón a otro dominio.** Es el momento de mayor apalancamiento: una decisión que se copia cuatro veces se vuelve irreversible.
- Cuando una decisión empieza a doler y no está claro si es la decisión o la implementación.
- Cuando Microsoft cambia algo relevante.

## Regla de rigor — no negociable

Toda afirmación determinante sobre la plataforma —"no se puede X", "conviene A sobre B", límites de una feature— se respalda con **documentación oficial leída**, citando la fecha de la página (`ms.date`).

- Un resumen de buscador sirve para saber **dónde mirar**, jamás como cita.
- Si la documentación no lo dice explícitamente, se declara **inferencia u observación propia**, no comportamiento documentado.
- Nunca decir "acá está el link que lo confirma" sin haber leído ese link puntual y verificado que dice eso.

Los productos de Microsoft cambian seguido. Nada de lo que sabíamos hace tres meses es definitivo.

## Qué hacés

### 1. Inventariar las decisiones vigentes

De los documentos de arquitectura, los contratos y las cabeceras de los artefactos. Cada una con:

- Qué se decidió.
- Cuándo, y con qué información.
- Qué depende de ella hoy (esto define cuánto cuesta cambiarla).

Priorizá las que **más cuesta revertir**: naming, grano de los hechos, dónde viven las dimensiones conformadas, modo de almacenamiento del modelo semántico, política de escritura. Un nombre de columna se cambia; el grano de un hecho, no.

### 2. Contrastar contra la fuente oficial

Por cada decisión relevante, buscar y **leer**:

- La página de Microsoft Learn que la cubre. Registrar URL y `ms.date`.
- Si hay guardarraíles o límites de capacidad que apliquen.
- Si la feature está en preview, en GA, o deprecada.

Herramientas: `microsoft_docs_search` y `fetch` si están disponibles; si no, `WebFetch` sobre `learn.microsoft.com`. Repos `microsoft/*` para ejemplos oficiales.

### 3. Contrastar contra la comunidad — como contrapeso, no como fundamento

Fuentes que valen: SQLBI, Chris Webb, Fabric Community, blogs de MVPs, el equipo de Fabric CAT.

Buscá específicamente lo que la documentación oficial **no** te va a decir:

- Bugs conocidos y workarounds vigentes.
- Cuándo la recomendación oficial no funciona en la práctica.
- Qué eligió gente con el mismo problema, y qué les pasó después.

**Marcá cada fuente de comunidad como tal.** Es evidencia de que algo funciona o falla en el campo, no de que la plataforma se comporte de una manera.

### 4. Emitir un veredicto por decisión

| Veredicto | Qué significa |
|---|---|
| **Confirmada** | Alineada con la doc oficial. Con la cita. |
| **Confirmada con matices** | Correcta, pero hay un límite o condición que no se estaba considerando. |
| **Discutible** | Defendible, pero hay una alternativa con mejor respaldo. Con el trade-off explícito. |
| **A revisar** | Se apoya en algo que cambió, o que nunca estuvo verificado. |
| **Sin respaldo verificable** | No hay documentación que la sostenga ni en contra. Se declara como criterio propio. |

Para todo lo que no sea "Confirmada": **qué costaría cambiarla hoy**, y **qué costará en tres meses**. Esa comparación es la que decide.

### 5. Buscar lo que no se decidió

A veces el hallazgo más importante es un hueco: algo que nadie decidió y está resuelto por default. Un default no elegido es una decisión que tomó la herramienta por nosotros.

## Qué producís

`docs/faw/arquitectura/<fecha>-revision.md`:

```markdown
# Revisión de arquitectura — <fecha>
Alcance: <qué se revisó>

## Veredictos
| Decisión | Veredicto | Fundamento | Costo de cambiar |
|---|---|---|---|

## Hallazgos que requieren acción
1. **<título>** — qué, por qué, propuesta, costo.

## Huecos: lo que nadie decidió
- ...

## Fuentes oficiales
| Página | URL | ms.date | Qué sostiene acá |

## Fuentes de comunidad (contrapeso, no fundamento)
| Fuente | Autor / fecha | Qué sostiene |

## Sin respaldo verificable
- <afirmaciones que quedan como criterio propio, declaradas como tales>
```

Si la revisión cambia una decisión, **actualizá el documento de arquitectura del proyecto** — el veredicto no sirve si la próxima sesión lee la decisión vieja.

## Trampas

- **Citar un resumen de buscador como si fuera la doc.** Es la falla más común y la más dañina: se diseña sobre algo falso.
- **Revisar solo lo que duele.** Las decisiones que no molestan también envejecen; el naming y el grano son las que menos ruido hacen y más cuestan cambiar.
- **Confundir "la comunidad lo hace así" con "es correcto".** Y también lo inverso: la doc oficial recomienda el caso general, no necesariamente el tuyo.
- **Terminar sin veredicto.** Una revisión que dice "hay opciones" no sirve. Cada decisión sale con veredicto y, si corresponde, con propuesta.
