# FAW — Guía completa

> **Documento único y canónico de FAW.** Todo lo que hay que saber para trabajar con el método, y suficiente para explicarlo en detalle sin consultar nada más. Escrito para entenderlo, no para hojearlo.
>
> Versión **v2**. Es el único documento de referencia del método. Lo que se lee aparte, porque es lo que el agente carga en cada turno, son las reglas operativas en [`faw/reglas/`](faw/reglas/).
>
> **Cómo leerlo la primera vez:** §1 y §2 dan el porqué. §3 a §7 son el método. **§7b es la mecánica por dentro** — la sección que hace falta para explicarlo. §10b es un ciclo completo con los comandos reales. §15 es cómo instalarlo.

---

## 1. Qué problema resuelve, en una idea

En software el artefacto es código y el fallo es ruidoso: si algo se rompe, compila mal o el test rojo lo grita. En una plataforma de datos el artefacto es una tabla, y **el fallo característico es un número creíble y falso.**

Esta semana sola dio el catálogo completo:

- Una dimensión de calendario publicada con **11 de 23 columnas**. Se validó mirando que las filas coincidieran (4.019, correcto) y se dio por buena.
- Tres relaciones de un modelo semántico apuntando **todas a la misma columna** del fact, por aceptar el default de un diálogo tres veces seguidas.
- Un commit "de formato" que de paso **borró el lakehouse por defecto** de tres notebooks — no se vio porque el diff mostrado en pantalla no llegaba hasta el encabezado.
- FKs de fecha nulas: una partida que desaparece del total en cuanto alguien filtra por fecha, sin ningún error.

Ninguno de los cuatro lo atrapa un test unitario, un linter o un code review. Los cuatro se detectaron midiendo contra datos reales — algunos tarde. FAW existe para que esa medición no dependa de que a alguien se le ocurra hacerla.

**La idea que ordena todo:** evidencia antes que declaración. Un número sin la consulta que lo produjo no es un dato, es una opinión con formato de dato.

## 2. De dónde sale

Inspirado en [dilux-agentic-workflow (DAW)](https://github.com/soydiloreto/dilux-agentic-workflow), un método para pipelines de desarrollo de software con seis fases y compuertas.

Tomé cuatro ideas de ahí: fases con compuertas aplicadas fuera del modelo, tiers para no cobrar caro lo barato, la escala honesta de qué respalda cada compuerta, y que valide quien no construyó.

No tomé la implementación — es un plugin para seis herramientas distintas y resuelve problemas que yo no tengo. Lo que cambia de fondo es el objeto: DAW verifica que el código compile y los tests pasen; FAW verifica que una tabla tenga las columnas que dice tener y que un modelo semántico apunte a donde dice apuntar.

**El mecanismo de aplicación, no solo la arquitectura.** Copiar las fases sin lo que las hace cumplir deja reglas escritas que nadie corre. Cuatro piezas concretas:

| De DAW | Por qué |
|---|---|
| **Distribuirse como plugin** | Instalación en un paso: las skills y el agente quedan disponibles como comandos, no solo escritos en el repo |
| **Un hook que pone el método delante del modelo** | DAW usa `SessionStart`; FAW usa `UserPromptSubmit`, que corre en cada turno y sobrevive la compactación y el `/clear` |
| **Línea de estado obligatoria en cada respuesta** | Cero código y es la señal más temprana de desvío. Ahora es el principio 13 |
| **El gotcha del archivo de hooks** | No usar el default `hooks/hooks.json`: lo comparten varias herramientas y Claude descarta el archivo entero, en silencio, si encuentra un evento ajeno. DAW lo midió |

**La diferencia arquitectónica que faltaba entender.** FAW v1 puso las compuertas en **scripts que el agente invoca**; DAW las puso **alrededor del archivo de estado**, y el estado gobierna qué se puede hacer. En DAW no se avanza de fase sin que un hook valide la transición. En FAW v1 se podía, simplemente, no llamar a `estado.py`. La v2 cierra eso con el hook de escritura, que exige que la clasificación exista antes de la primera edición.

## 3. Las siete clasificaciones (tiers)

Lo primero que pasa con cualquier pedido: se le asigna un tier, se explica por qué en una línea, y se espera el OK.

| Tier | Qué es | Recorrido | Ejemplo |
|---|---|---|---|
| **CONSULTA** | Una pregunta | No entra al grafo. Se responde y termina. | *"¿qué es TMDL?"* |
| **EXPLORACIÓN** | Entender sin tocar nada | CLASIFICACIÓN → PERFILADO → documento | Comparar Import contra Direct Lake para un caso |
| **CAMBIO-MENOR** | Ajuste acotado | CLASIFICACIÓN → CONSTRUCCIÓN → PUBLICACIÓN | Reasignar el lakehouse por defecto de tres notebooks |
| **ARTEFACTO** | Tabla, notebook, pipeline | Las seis fases completas | Una dimensión de calendario y sus tablas de rol; una columna derivada de un fact |
| **MODELO** | Modelo semántico | Las seis, verificado por API | Un modelo en Direct Lake sobre Gold |
| **REPORTE** | Reporte Power BI | Brief acordado, después construcción libre | Un tablero de antigüedad de saldos |
| **INCIDENTE** | Algo roto | CLASIFICACIÓN → PERFILADO del síntoma → CONSTRUCCIÓN → PUBLICACIÓN | Un notebook sin lakehouse por defecto; una tabla publicada incompleta |

`MODELO` y `REPORTE` son tiers separados porque lo que se puede verificar por máquina es distinto en cada uno. En un modelo semántico —relaciones, storage mode, propiedades de columna— la definición se consulta por API y se compara contra lo declarado. En un reporte, el layout y la elección de visual no son verificables por máquina, y el desarrollo es iterativo. Cobrarle al reporte el rigor del modelo sería una compuerta que no se puede satisfacer honestamente, y esas no deben existir.

`CAMBIO-MENOR` tiene guardarraíl: si el cambio toca esquema, lógica de negocio, capa de consumo, o supera ~30 líneas, se para y se reclasifica a `ARTEFACTO`. No es criterio del agente — es una condición explícita.

`CONSULTA` **no entra a la máquina de estados**. No abre ticket, no toca `.faw/estado.jsonl`. Meterla adentro habría sido la clase de ceremonia que hace abandonar un método.

## 4. El grafo

`faw/transiciones.json` es un **grafo dirigido**, no una lista de reglas.

- **Nodos**: las fases (`CLASIFICACIÓN`, `PERFILADO`, `DISEÑO`, `CONSTRUCCIÓN`, `VALIDACIÓN`, `PUBLICACIÓN`) más `IDLE`.
- **Aristas**: los movimientos permitidos. No todo nodo conecta con todo nodo — desde `CONSTRUCCIÓN` solo se puede ir a `VALIDACIÓN`, nunca saltar a `PUBLICACIÓN`.
- **Cada arista puede tener compuertas** que hay que satisfacer para cruzarla.

`scripts/estado.py` camina ese grafo: mira en qué nodo estoy parado, si la arista pedida existe para el tier activo, y si sus compuertas pasan. Si no, rechaza la transición en código — no queda a criterio del momento.

**Los tiers son caminos distintos sobre el mismo grafo**, no grafos separados:

```
ARTEFACTO / MODELO:
  CLASIFICACIÓN ──► PERFILADO ──► DISEÑO ──► CONSTRUCCIÓN ──► VALIDACIÓN ──► PUBLICACIÓN ──► IDLE
     ▲(1)                       ▲(2)                         │  ▲(3)
     └── confirmación ──────────┘                      falla └──┘
                                                          vuelve a CONSTRUCCIÓN

CAMBIO-MENOR:
  CLASIFICACIÓN ──────────────────────────► CONSTRUCCIÓN ──────────────────► PUBLICACIÓN ──► IDLE

REPORTE:
  CLASIFICACIÓN ──brief──► CONSTRUCCIÓN (libre) ───────────► PUBLICACIÓN ──► IDLE
     ▲(1)                                        ▲(2)
     └── confirmación                       confirmación

CONSULTA:
  (no entra al grafo)
```

`(1)(2)(3)` son los tres únicos puntos donde el proceso para a esperarme — ver §7.

## 5. Las seis fases, qué hace cada una

**1. CLASIFICACIÓN.** Reformular el pedido en una frase, mirar el estado real (rama, working tree, `.faw/estado.jsonl`), asignar tier, decidir qué entra y **qué no**. Abrir rama si corresponde.

**2. PERFILADO.** La fase que un pipeline de software no tiene. Los requisitos de datos están la mitad en el origen y solo se descubren midiendo: la clave natural se prueba (`count(*)` vs `count(distinct)`), no se copia de una ficha vieja. Cada número va con la consulta que lo produjo. Es solo lectura — si hace falta escribir para perfilar, autorización explícita antes.

**3. DISEÑO.** Grano en una frase ("una fila por ___"), clave natural verificada, contrato de datos en `.yml`, dónde vive cada transformación (*"si al borrar el consumidor de hoy la transformación deja de tener sentido, no va en la capa de abajo"*), riesgos traducidos a aserciones concretas.

**4. CONSTRUCCIÓN.** Se implementa y se corre contra DEV, con las validaciones **adentro** del artefacto (no en un script aparte, para que corran en cada ejecución futura). Se reporta filas y columnas, nunca solo filas.

**5. VALIDACIÓN.** La ejecuta el agente `faw-validador`, que **no construyó** y no recibe el razonamiento de construcción. Compara el esquema real contra el contrato, columna por columna; los números del artefacto contra el perfilado; corre `verificar_modelo.py` si aplica. Busca refutar, no confirmar — es exactamente lo que faltó en el caso de las 11/23 columnas. Si falla, vuelve a CONSTRUCCIÓN. **No se parchea acá**: el parche lo escribiría el validador y ya no queda nadie mirando desde afuera.

**6. PUBLICACIÓN.** Verificar el diff completo (`verificar_diff.py`, ahora también como hook), PR, merge, sincronizar el workspace, verificar que los artefactos conserven su lakehouse por defecto, actualizar el tracker.

## 6. Las compuertas — qué respalda a cada una, sin inflar

| Compuerta | Fuerza | Qué la respalda |
|---|---|---|
| `git-limpio` | **Máquina** | `git status --porcelain` directo |
| `esquema` | **Máquina** | `verificar_contrato.py` compara la tabla real contra el contrato, columna por columna |
| `modelo` | **Máquina** | `verificar_modelo.py` compara la definición del modelo semántico por API |
| `reporte` | **Máquina** | `verificar_reporte.py` — campos huérfanos y filtros persistidos en el PBIR |
| `metadata` | **Máquina** | `verificar_diff.py` lee el diff completo; además hookeado a `git commit` |
| `plataforma` | **Máquina** | `verificar_plataforma.py` exige que cada literal de Microsoft (`$schema`, connection string) tenga precedente en el repo o resuelva HTTP 200 |
| `brief` | **Máquina** | `verificar_brief.py` mide el contenido útil de cada sección del brief y rechaza el template sin llenar |
| `perfil` | Recibo | Existe `docs/faw/<ticket>/perfilado.md` con consultas |
| `contrato` | Recibo | El contrato existe y es sintácticamente válido |
| `aserciones` | Declaración | Registro del agente de que corrieron y pasaron |
| `autorizacion` | Declaración | Registro del OK explícito para escribir en el tenant |
| `reconciliacion` | Declaración | Registro de la comparación contra fuente independiente, con responsable nombrado |
| `confirmacion_usuario` | Declaración | El registro de que el usuario dio el OK en un punto de control |

### El agujero que tenía esto, y cómo se cerró

La primera versión vendía cuatro compuertas "de máquina" y en el código solo una lo era: `estado.py` aceptaba que yo escribiera `--compuerta esquema="ok: nunca corrí nada"` y avanzaba igual. Lo reproduje yo mismo antes de creerle a nadie: `VALIDACION -> PUBLICACION` con esa mentira, exit 0. El método se descalificaba con su propia frase — *"una compuerta a la que se le puede mentir convierte a todas las demás en sugerencias"*.

**El arreglo: recibos firmados por el propio verificador** (`faw/recibos.py`). Cada script, al pasar, escribe un JSON con el **hash de cada archivo que verificó** más el commit. `estado.py` exige ese recibo y **recomputa los hashes** — si el contrato cambió después de emitirse el recibo, el recibo queda vencido.

Probado de punta a punta:
- Avanzar sin correr el verificador → rechazado.
- Correr el verificador y avanzar → pasa.
- Modificar el contrato después del recibo → `recibo vencido: cambio desde que se emitio`.

**Hasta dónde llega esto, sin adornos:** convierte el bypass accidental en imposible, y el deliberado en un acto explícito y rastreable (fabricar un JSON con los hashes correctos a propósito). **No lo hace infalsificable de raíz** — sin un secreto que yo no pueda leer, ningún archivo local lo es. La irrevocabilidad real la da el hook, que corre fuera de la conversación.

## 7. Los puntos de control (y por qué no son más)

Un ciclo `ARTEFACTO` completo tenía, en la primera versión, entre 9 y 11 paradas — se conté al escribir la fricción real. Ese es el tipo de proceso que se abandona en dos semanas.

**Se recortó a 3**, y solo esos tres piden confirmación de proceso:

1. **Fin de CLASIFICACIÓN** — ¿el tier y el alcance son correctos?
2. **Fin de DISEÑO** — ¿el contrato y el plan están bien, antes de gastar tiempo construyendo? Es el punto de mayor apalancamiento: acá una decisión mala cuesta más barato que después.
3. **Fin de VALIDACIÓN** — ¿se publica esto, viendo el veredicto del validador independiente?

Las demás transiciones —entrar a DISEÑO ya perfilado, entrar a VALIDACIÓN ya construido, cerrar PUBLICACIÓN— **avanzan solas** apenas sus compuertas técnicas están satisfechas. Se ve un resumen con números, no se espera un OK de proceso.

**Los tres son el recorrido de `ARTEFACTO` y `MODELO`. Cada tier tiene los suyos:**

| Tier | Puntos de control |
|---|---|
| `ARTEFACTO`, `MODELO` | 3: fin de CLASIFICACIÓN, fin de DISEÑO, fin de VALIDACIÓN |
| `REPORTE` | 2: fin de CLASIFICACIÓN (**con el brief acordado**), y antes de publicar |
| `CAMBIO-MENOR`, `INCIDENTE`, `EXPLORACION` | 0 de proceso — avanzan por compuertas técnicas |
| `CONSULTA` | 0 — no entra al grafo |

El del `REPORTE` está a la entrada por una razón precisa: sin punto de control ahí, "construcción libre" se lee como "no hace falta acordar nada", y el reporte se construye sobre un alcance supuesto.

**Esto no toca la autorización para escribir en el tenant.** Esa se pide siempre, en cada escritura, sin excepción — es una regla de seguridad, no un punto de control de proceso, y no se cuenta contra el recorte.

## 7b. La mecánica, por dentro

Esta sección es la que falta para poder explicar FAW sin handwaving. Son cuatro piezas y se entienden mejor en orden.

### El archivo de estado: `.faw/estado.jsonl`

Vive **en el repo de trabajo**, no en FAW. Cada proyecto tiene el suyo, y su existencia es lo que activa el método (§15). Es **append-only**: una línea JSON por transición, nunca se reescribe. Una línea típica:

```json
{"ticket": "T-31", "tier": "REPORTE", "titulo": "Antigüedad de saldos",
 "fase": "CONSTRUCCION", "desde": "2026-08-04T19:30:51+00:00"}
```

Que sea append-only no es prolijidad: es lo que permite reconstruir **qué se decidió y cuándo** después de cerrar la sesión. El estado actual es simplemente la última línea.

> Compatibilidad: un `estado.jsonl` puede contener el nombre viejo de la fase 1 (`ENCUADRE` en vez de `CLASIFICACION`). Es inofensivo (los hooks y `estado.py` leen solo la última línea), salvo que haya un trabajo **pausado en esa fase**, en cuyo caso se edita esa última línea a mano antes de reanudar.

### El grafo: `faw/transiciones.json`

Un grafo dirigido, no una lista de reglas. Los nodos son las fases más `IDLE`; las aristas, los movimientos permitidos; cada arista lleva sus compuertas. Los tiers **no son grafos separados**: son caminos distintos sobre el mismo grafo. Por eso `CONSTRUCCION -> PUBLICACION` existe en `REPORTE` y no en `ARTEFACTO`, donde hay que pasar por `VALIDACION`.

`scripts/estado.py` camina ese grafo: mira dónde está parado, si la arista pedida existe **para el tier activo**, y si sus compuertas pasan. Si algo falla, rechaza la transición y explica cuál compuerta y por qué. No queda a criterio del momento.

### Los recibos: `faw/recibos.py` y `.faw/recibos/*.json`

Es la pieza que arregló el agujero de la primera versión. Antes, `estado.py` aceptaba `--compuerta esquema="ok, verifiqué"` y avanzaba: una compuerta "de máquina" satisfecha con una afirmación.

Ahora cada verificador, **al pasar**, escribe un recibo con:

- qué compuerta pasó y con qué script,
- el **hash SHA-256 de cada archivo que verificó**,
- el commit en el que se emitió,
- la fecha y un detalle.

Y `estado.py`, al evaluar la compuerta, **recomputa los hashes**. Si el contrato cambió después de emitirse el recibo, el recibo está vencido y la compuerta se cierra. Eso es lo que impide perfilar una vez, cambiar el diseño, y seguir usando el recibo viejo.

**Hasta dónde llega, sin adornos:** un recibo eleva el costo de falsear de "escribir un string" a "fabricar un JSON con los hashes correctos, a propósito". Elimina el bypass accidental y convierte al deliberado en un acto explícito y rastreable. **No lo hace imposible**: sin un secreto que el agente no pueda leer, ningún archivo local es infalsificable. La irrevocabilidad real la dan los hooks, que corren fuera de la conversación.

### Las tres fuerzas de compuerta, y por qué la distinción importa

| Fuerza | Cómo se satisface | Se le puede mentir |
|---|---|---|
| **Máquina** | Corriendo su script, que emite el recibo. `estado.py` recomputa hashes | No por accidente |
| **Recibo** | Existe un archivo con contenido mínimo, y el agente declara su ruta | Con un archivo de relleno |
| **Declaración** | El agente registra una afirmación con `--compuerta clave="texto"` | Sí, y está marcado como tal |

Que las declaraciones estén etiquetadas **como declaraciones** es lo que hace confiables a las demás. Una compuerta a la que se le puede mentir sin avisar convierte a todas en sugerencias.

## 8. El canal de cambio

La pregunta de todos los días: ¿esto va por PR, por Livy, o directo en la UI de Fabric?

> **El criterio: el canal lo decide dónde tiene que quedar el registro.**

| Qué | Canal | Aprobación | Registro |
|---|---|---|---|
| Notebook, código de pipeline | Git + PR | Al mergear | Commit |
| Contrato de datos, documentación | Git + PR | Al mergear | Commit |
| Leer datos, perfilar, diagnosticar | Livy | Ninguna — es lectura | El recibo de perfilado |
| Correr un notebook contra DEV | Livy o UI | **OK explícito del turno** | `ctrl.control_ingesta` + el cierre |
| Escribir/borrar una tabla en DEV | Livy | **OK explícito**, con tabla/operación/filas | Ídem, y regenerable desde un artefacto commiteado |
| Canvas de pipeline, permisos, shortcuts | UI de Fabric | Al commitear | Commit del workspace |
| Modelo semántico, reporte | UI o Desktop | Al commitear | Commit + `verificar_modelo.py` / `verificar_reporte.py` |
| Cualquier cosa en PRD | Deployment Pipeline | **OK explícito**, siempre | Historial del deployment |

Tres reglas que se desprenden:

1. **Livy en lectura es libre; en escritura, nunca sin OK.** Y toda escritura por Livy tiene que ser **regenerable desde un artefacto commiteado** — si la lógica que la produjo solo existió en una sesión ya cerrada, no es un cambio, es un accidente que nadie puede reproducir.
2. **Git es la fuente de verdad de todo lo serializable.** El workspace es destino de despliegue, no lugar de edición. Excepciones explícitas: lo que no tiene otra superficie.
3. **Nada llega a PRD sin OK explícito**, sin excepción por tamaño.

**Lo que no se puede bloquear, dicho así:** Livy ejecuta código Spark arbitrario. Ningún hook puede inspeccionarlo antes de que corra. Ahí el método detecta (queda en `ctrl.control_ingesta`), no previene. Prometer prevención sobre Livy sería mentir sobre una compuerta.

## 9. Cuándo se activa el flujo

**Todo pedido pasa por CLASIFICACIÓN** — clasificar es una frase, no cuesta nada. Lo que cambia es qué pasa después: `CONSULTA` se responde y no toca el estado; el resto sí abre ticket.

**Pedido a mitad de otro trabajo:**

| Situación | Qué pasa |
|---|---|
| Es una `CONSULTA` | Se responde, no se toca el estado |
| Es parte del alcance abierto | Se hace dentro del trabajo actual |
| Es otra cosa, y lo actual está en un punto estable | Se pausa lo actual (queda el punto de retomada), se clasifica lo nuevo |
| Es otra cosa, y lo actual está a mitad de una escritura | Se termina el paso en curso primero |
| Es un `INCIDENTE` | Se pausa sin preguntar, arranca. Lo roto gana |

Siempre se dice qué se hace con lo anterior. Cambiar de tarea en silencio es cómo se pierde el hilo.

**Varios pedidos en un mismo mensaje:** se clasifican todos juntos, se confirma una sola vez, se ejecutan en orden con su propio estado cada uno. No hay tres rondas de confirmación para un solo mensaje.

## 10. Los instrumentos, uno por uno

**Skills** (`skills/faw-*`) — instrucciones que se cargan en el contexto del agente al arrancar una fase o una tarea puntual. Le dicen qué medir, qué producir, en qué trampas caer. No obligan a nada por sí solas: son la parte que depende de que el agente las lea y cumpla.

- `faw-clasificar` — fase 1.
- `faw-perfilar` — fase 2.
- `faw-validar` — lanza al validador independiente en fase 5.
- `faw-backlog` — trae el sprint de Azure DevOps, propone con qué seguir, reconcilia pedidos fuera de backlog.
- `faw-roadmap` — cruza ADO, tracker interno y la realidad de Fabric; propone reencauzar.
- `faw-arquitectura` — contrasta decisiones contra doc oficial de Microsoft y comunidad.

**Contratos** (`faw/contratos/*.yml`) — declaran grano, clave natural, columnas con tipo y nulabilidad, reglas de calidad, consumidores. Se escriben en DISEÑO, antes de construir. Sin esto no hay nada contra qué comparar el esquema real — es literalmente lo que faltaba cuando la dimensión salió con 11 de 23 columnas.

**Scripts** (`scripts/*.py`) — comparan la realidad contra lo declarado y devuelven exit code. No dependen de mi buena voluntad para correr, aunque sí de que alguien los invoque (todavía, salvo el que ya está hookeado):

- `verificar_contrato.py` — compuerta `esquema` y `contrato`.
- `verificar_diff.py` — compuerta `metadata`. Ya probado contra el commit real que perdió el binding de lakehouse: lo detectó, exit 1.
- `verificar_modelo.py` — compuerta `modelo`.
- `verificar_reporte.py` — compuerta `reporte`: campos huérfanos contra el modelo y filtros persistidos en el PBIR. **Declarado como heurística de primera iteración** — no tengo la especificación oficial del formato PBIR verificada en este momento contra la doc de Microsoft, así que hay que afinarlo contra un `.pbip` real la primera vez que se use en serio. Es exactamente la regla de rigor de FAW aplicada a sí mismo: no inventar comportamiento de la plataforma sin haberlo leído.

**Agente validador** (`agents/faw-validador.md`) — corre la fase VALIDACIÓN. No construyó, no corrige. Existe porque quien construye valida buscando confirmación, no refutación.

**Estado** (`scripts/estado.py` + `.faw/estado.jsonl`) — la máquina que camina el grafo. Valida el tier al iniciar, exige recibos (no declaraciones) en las compuertas de máquina, permite pausar y **reanudar**, reentrando exactamente en la fase donde se pausó.

**Hooks — la capa que hace real todo lo anterior.** Sin ellos, el método depende de que el agente se acuerde de leerlo. Son cuatro, instalados por el plugin:

| Hook | Evento | Qué hace |
|---|---|---|
| `inyectar_contexto.py` | `UserPromptSubmit` | Inyecta en **cada turno** fase, tier, ticket, la regla de esa fase, la skill de Microsoft que aplica y las salidas legales. Sobrevive compactación y `/clear`, que es donde se pierde la clasificación |
| `compuerta_escritura.py` | `PreToolUse` (Write/Edit) | Deniega escribir sin CLASIFICACIÓN registrado, y deniega escribir durante PERFILADO (que es solo lectura). Excepción: los recibos en `docs/faw/` |
| `compuerta_pr.py` | `PreToolUse` (Bash) | Corre el checklist de `cliente.md` sobre el `--body` de un `gh pr create/edit` antes de que el PR exista |
| `pre_commit_metadata.py` | `PreToolUse` (Bash) | Bloquea un commit que toca metadata protegida sin declararlo, **y corre la compuerta `plataforma` sobre el diff staged** (literales de Microsoft inventados). Ambas con override de un solo uso en `.faw/*-permitida.txt` |

Todos son **opt-in**: salen sin hacer nada si el proyecto no tiene `.faw/`. FAW instalado global no mete contexto de Fabric en un proyecto que no es de Fabric.

Dos cosas aprendidas construyéndolos, las dos probando y no razonando: en Windows **stdout es cp1252**, así que un emoji o un acento hace crashear el hook — y un hook que crashea sale con código ≠ 0, que la doc trata como *no bloqueante*, o sea que FAW quedaría instalado sin hacer cumplir nada, en silencio. Y `disallowed-tools` de una skill **no sirve** para sostener una fase de solo lectura: la doc dice que esa restricción se limpia con el siguiente mensaje del usuario.

**Detalle del hook original** (`faw/hooks/pre_commit_metadata.py`) — el primero que existió. Intercepta cualquier `git commit` antes de que exista, corre `verificar_diff.py`, y si encuentra metadata protegida sin declarar, **bloquea la llamada a la herramienta** (exit 2, verificado contra la doc oficial de Claude Code). Se instala fusionando `adapters/claude/settings.snippet.json` en el `.claude/settings.json` del proyecto — ese bloque se versiona con el repo, no es config por máquina como pensé al principio. Probado: bloquea sin declarar, permite con `.faw/metadata-permitida.txt` (se consume solo, no queda de bypass permanente), ignora cualquier comando que no sea un commit.

Lo que este hook **no** cubre: Livy. Ver §8.

**Autoverificación** (`scripts/autoverificar.py`) — un canary de las propias compuertas: por cada verificador, arma en un directorio temporal un caso que debería pasar y uno con un defecto puntual conocido que debería fallar, y confirma que cada uno se comporta como se espera. No prueba que el proyecto de trabajo esté bien — prueba que los verificadores mismos no se rompieron con el tiempo (un cambio accidental en una regex, una condición invertida). Nace de leer completo el `mutate.py` de DAW: su enfoque (mutar código y correr la suite completa contra ~100 mutaciones) está fuertemente acoplado a infraestructura que FAW no tiene; lo que se adoptó fue la idea de fondo — "es el medidor, no el detector" — expresada como insumos bueno/malo, no como mutación de código.

## 10b. Un ciclo completo, con los comandos reales

Un `ARTEFACTO` de punta a punta. Es la sección para tener a mano la primera vez. Los ejemplos asumen FAW clonado en `~/faw` — reemplazá por tu ruta.

```bash
# --- CLASIFICACIÓN -------------------------------------------------------------
# El hook de UserPromptSubmit ya inyectó "[FAW] Sin trabajo clasificado".
# Se clasifica, se define alcance, se espera el OK del usuario. Recién después:
python ~/faw/scripts/estado.py iniciar \
    --ticket T-42 --tier ARTEFACTO --titulo "fact_<entidad>"

# Antes de esto, el hook de escritura deniega cualquier Write/Edit.

# --- PERFILADO ------------------------------------------------------------
python ~/faw/scripts/estado.py mover --a PERFILADO \
    --compuerta confirmacion_usuario="OK del usuario al tier y alcance"

# Se mide contra el origen. El hook deniega escrituras acá, salvo el recibo:
#   docs/faw/T-42/perfilado.md   <- cada número con su consulta

# --- DISEÑO ---------------------------------------------------------------
python ~/faw/scripts/estado.py mover --a DISENO \
    --compuerta perfil=docs/faw/T-42/perfilado.md

# Se escribe el contrato y se valida su sintaxis (emite recibo POR TABLA):
python ~/faw/scripts/verificar_contrato.py --solo-sintaxis \
    --contrato faw/contratos/dbo.fact_<entidad>.yml

# --- CONSTRUCCIÓN ---------------------------------------------------------
python ~/faw/scripts/estado.py mover --a CONSTRUCCION \
    --compuerta confirmacion_usuario="OK del usuario al diseño y al contrato"

# Si el ticket toca MÁS DE UNA tabla: correr verificar_contrato.py por cada
# una y declarar el alcance en el mover, que exige el recibo de CADA tabla:
#   --compuerta tablas=dbo.fact_movimiento_caja,dbo.dim_cuenta,...
# Sin la declaración, con varios recibos emitidos el mover se rechaza: la
# máquina no adivina cuántas tablas toca el ticket.

# PASO 0: leer la skill oficial de Microsoft que aplique. Después construir.
# Cada escritura al tenant se autoriza en el turno, no una vez al principio.

# --- VALIDACIÓN -----------------------------------------------------------
python ~/faw/scripts/estado.py mover --a VALIDACION \
    --compuerta aserciones="clave natural sin duplicados, esquema OK, 2.705 filas" \
    --compuerta autorizacion="OK explícito para escribir dbo.fact_movimiento_caja"

# Lo corre faw-validador, que no construyó (emite recibo POR TABLA — con
# varias tablas aplica la misma declaración `tablas=` que en CONSTRUCCIÓN):
python ~/faw/scripts/verificar_contrato.py \
    --contrato faw/contratos/dbo.fact_<entidad>.yml --esquema esquema_real.json

# --- PUBLICACIÓN ----------------------------------------------------------
python ~/faw/scripts/estado.py mover --a PUBLICACION \
    --compuerta confirmacion_usuario="OK del usuario al veredicto del validador"

python ~/faw/scripts/verificar_plataforma.py     # literales de Microsoft
python ~/faw/scripts/verificar_diff.py           # metadata protegida
git commit ...                                           # el hook lo revisa antes
gh pr create ...                                         # el hook revisa el body

# --- CIERRE ---------------------------------------------------------------
python ~/faw/scripts/estado.py mover --a IDLE     # exige git limpio
```

**Un `REPORTE` es más corto**, y su única diferencia relevante está al principio:

```bash
python ~/faw/scripts/estado.py iniciar --ticket T-50 --tier REPORTE --titulo "..."
# Se acuerda el brief CON el usuario y se escribe docs/faw/T-50/brief.md
python ~/faw/scripts/verificar_brief.py --ticket T-50
python ~/faw/scripts/estado.py mover --a CONSTRUCCION \
    --compuerta confirmacion_usuario="OK del usuario al brief"
```

**Pausar y retomar**, que es lo que hace que el método sobreviva cerrar la sesión:

```bash
python ~/faw/scripts/estado.py pausar --motivo "espero confirmación de Contabilidad"
python ~/faw/scripts/estado.py reanudar    # reentra en la fase exacta
python ~/faw/scripts/estado.py estado      # dónde estoy y qué salidas tengo
```

## 10c. Referencia de comandos

| Comando | Para qué |
|---|---|
| `estado.py estado` | Fase, tier, ticket y salidas legales con sus compuertas |
| `estado.py iniciar --ticket --tier --titulo` | Abre el trabajo. Valida el tier contra el grafo |
| `estado.py mover --a FASE [--compuerta k=v]` | Transición. Rechaza si la arista no existe o falta una compuerta |
| `estado.py pausar --motivo` / `reanudar` | Corta y retoma en la misma fase |
| `estado.py abandonar --motivo` | Cierra sin publicar, dejando el por qué |
| `verificar_contrato.py` | Compuertas `esquema` y `contrato`. Columna por columna |
| `verificar_diff.py` | Compuerta `metadata`. Lee el diff completo, incluido el encabezado |
| `verificar_modelo.py` | Compuerta `modelo`: relaciones, storage mode, `summarizeBy`, `sortByColumn` |
| `verificar_reporte.py` | Compuerta `reporte`: campos huérfanos y filtros persistidos en el PBIR |
| `verificar_brief.py --ticket T` | Compuerta `brief`: contenido útil por sección, rechaza el template |
| `verificar_plataforma.py [--todo] [--sin-red]` | Compuerta `plataforma`: literales de Microsoft con precedente o resolución |
| `autoverificar.py` | Canary: prueba que los verificadores no se rompieron con el tiempo |
| `claude plugin validate ~/faw` | Que el manifest del plugin sea válido |

## 10d. Cómo sé que está funcionando

Tres señales, de la más rápida a la más profunda:

1. **La línea de estado.** Si una respuesta no arranca declarando fase y ticket, el principio 13 no se está cumpliendo — y es el síntoma más temprano de que tampoco se están cumpliendo los demás.
2. **La inyección por turno.** Se comprueba a mano:
   ```bash
   echo '{"cwd":"C:/ruta/al/repo"}' | python ~/faw/faw/hooks/inyectar_contexto.py
   ```
   Si no imprime JSON, el proyecto no tiene `.faw/` (no está activado) o el hook está fallando.
3. **Los hooks bloquean de verdad.** La prueba es intentar la acción prohibida y ver la denegación: pedir un Write con el estado en `IDLE`, o crear un PR con un cuerpo largo. Si pasa, el plugin no está cargado.

**El modo de falla que más importa vigilar:** un hook que crashea sale con código ≠ 0, y la doc trata eso como *no bloqueante*. O sea que **un hook roto se ve igual que un hook que aprueba**. Ya pasó una vez (un emoji, en Windows, con stdout en cp1252). Por eso los hooks se prueban ejecutándolos, no leyéndolos.

## 11. Superficie de cliente

Antes de escribir en cualquier lado: **¿quién lo lee?**

FAW no distingue repos propios de repos de cliente: todo repo gobernado se trata como superficie de cliente, y cada commit y cada PR se escriben como si los leyera el destinatario del repo. El modo de fallo que esto cierra: un repo remoto se siente espacio de trabajo interno y no lo es — razonamiento de diseño, hallazgos abiertos o tareas asignadas a personas terminan publicados en la casa de quien los lee, sin que nada lo revise.

**Qué nunca va a una superficie de cliente:** hablar del cliente en tercera persona, asignar tareas a su gente, hallazgos abiertos y preguntas de negocio, alternativas descartadas y razonamiento extenso, metodología interna, atribución de IA.

**Qué sí va en un PR:** qué cambió, una línea de fundamento por decisión no obvia, números de validación, nota de despliegue si hace falta. Si pasa de una pantalla, sobra algo.

Lo específico de cada proyecto se declara en `.faw/config.json` (`personas_cliente` y `literales_internos`, ambas vacías por defecto); la compuerta `superficie` frena el commit o PR que lo contenga. Las rutas de artefactos del método (`docs/faw/`, `.faw/`) están exentas — si el lector del repo no debe verlas, se apuntan fuera con `artefactos_en` (fases.md).

Checklist antes de publicar: la palabra "cliente" refiriéndose a quien lo va a leer, nombres de personas del cliente con tarea asignada, secciones de hallazgos o pendientes, nombres de otros clientes o repos internos, cualquier mención de IA, más de una pantalla.

## 12. Los trece principios transversales

No dependen de fase ni tier:

1. **Evidencia antes que declaración.** Medido, estimado (y decirlo), o "no medido". Nunca una cuarta opción.
2. **Validar esquema, no solo conteo.** Filas y columnas, siempre.
3. **Autorización explícita por turno para escribir en el tenant.** Incluye lo temporal y lo "solo para verificar".
4. **El silencio es el enemigo.** Ninguna FK nula sin ir a un Desconocido visible; toda tabla con aserción de clave natural; un cambio de esquema no deseado falla, no pisa.
5. **Lo derivado se resuelve aguas arriba.** Las columnas en Gold, no en medidas del modelo — y Direct Lake ni siquiera soporta columnas calculadas.
6. **Afirmaciones sobre la plataforma: doc oficial leída**, con fecha de la página. Un resumen de buscador es pista, no cita.
7. **Saber quién lee cada superficie.** §11.
8. **No pelear con el serializador.** Si Fabric reformatea al importar, se acepta ese formato; nunca se revierte en un PR.
9. **Reproducir código a mano es peligroso.** Completo, nunca abreviado; comparar el esquema del resultado al terminar.
10. **El estado "success" de un job no es evidencia.** Un pipeline o notebook puede terminar "Succeeded" con 0 filas afectadas; se compara el delta real contra un mínimo esperado, nunca el status solo.
11. **Verificar contra el ambiente real, no contra el código.** El repo es la intención declarada; el workspace desplegado es la fuente de verificación — generaliza a la compuerta `metadata`.
12. **Una relación que publica sin error no está verificada.** El fact del lado "muchos" se confirma con un filtro real, relación por relación.
13. **La fase se declara en cada respuesta.** `{TIER} — {acción} | {ticket}: {título}`, o `[consulta]` si no toca nada. Es la regla más barata del método y la que más rápido expone que las demás no se están cumpliendo.

## 13. Backlog, roadmap y arquitectura

**`/faw-backlog`.** El MCP de ADO no ve todos los proyectos —hay al menos uno donde falla y no es permisos— así que la skill usa `az boards` directo cuando hace falta. Propone con qué seguir ordenando por **dependencia técnica**, no por el orden del backlog: las dimensiones antes que los hechos, siempre. Lo bloqueado no se propone, se reporta bloqueado. También reconcilia un pedido de chat contra las US existentes antes de proponer crear una nueva, y nunca crea ni cierra work items sin OK.

**`/faw-roadmap`.** Cruza tres estados que divergen con el tiempo: qué dice ADO, qué dice el tracker interno, y qué existe **de verdad** en Fabric. Las discrepancias son el material, no algo a esconder. Siete tipos de desvío con nombre (hecho-no-cerrado, cerrado-no-hecho, hecho-no-planificado, bloqueado-sin-dueño...), y por cada uno la causa: información del cliente, realidad técnica, estimación, o descubrimiento. No es reportar avance — es preguntarse si el plan sigue siendo el correcto.

**`/faw-arquitectura`.** Inventaría las decisiones más caras de revertir (naming, grano, dónde viven las conformadas, storage mode) y las contrasta contra Microsoft Learn leído (con `ms.date`) y contra la comunidad, marcada siempre como contrapeso y nunca como fundamento. Cinco veredictos posibles (Confirmada / con matices / Discutible / A revisar / Sin respaldo verificable), y para todo lo que no sea "Confirmada", el costo de cambiarla hoy contra el costo en tres meses. También busca los huecos: un default que nadie eligió es una decisión que tomó la herramienta.

## 13b. La capa de plataforma: skills oficiales de Microsoft

FAW no enseña a escribir un Eventstream ni qué API usar para desplegar un modelo — a propósito: ese conocimiento cambia con cada release y mantenerlo a mano garantiza que envejezca. Esa capa la mantiene Microsoft en [`microsoft/skills-for-fabric`](https://github.com/microsoft/skills-for-fabric) (MIT): skills operativas por tipo de artefacto, con decision trees de qué herramienta usar. Su propio repo declara que **no** trae compuertas ni contratos de datos — es exactamente el complemento de FAW, sin pisarse.

Se consume de un clon local (en los ejemplos, `~/skills-for-fabric`) — canal de instalación soportado oficialmente por su skill `check-updates` — y se actualiza con `git -C ~/skills-for-fabric pull --ff-only` (cadencia: si pasaron más de 7 días, al arrancar trabajo Fabric). Reglas de convivencia, mapa de qué skill leer para cada tipo de artefacto, y la alternativa de instalación como plugin nativo: [`faw/reglas/skills-microsoft.md`](faw/reglas/skills-microsoft.md). Las dos que gobiernan: **FAW manda en proceso, sus skills mandan en mecánica; y ninguna operación de escritura que ellas propongan exime del OK explícito del turno.**

## 14. Qué falta, a propósito

- Un hook sobre el MCP de Fabric que exija `autorizacion` antes de escrituras. Es el hueco más grande que queda: hoy la autorización para escribir en el tenant es una **declaración**, y el hook de escritura solo cubre `Write`/`Edit`/`NotebookEdit`. Una escritura por MCP o por Livy no pasa por ahí.
- **Escribir archivos con `Bash`** (heredoc, `>`, `tee`) tampoco pasa por el hook de escritura. Se podría cubrir agregando un matcher sobre `Bash`, y no está hecho todavía.
- **`autoverificar.py` todavía no cubre `verificar_brief.py` ni `verificar_plataforma.py`** — los dos verificadores nuevos se probaron a mano contra casos reales al construirse, pero el canary que detecta si se rompen con el tiempo solo cubre los cuatro originales.
- Un tier de orquestación de pipelines (dependencias, watermarks, concurrencia son su propia clase de fallo). Se espera a los primeros pipelines reales bajo el método antes de diseñarlo — la misma prudencia que se aplicó a DEV→PRD.
- Criterio de promoción DEV → PRD. Hueco real, dejado afuera a propósito: no hay criterio definido todavía, y escribir uno inventado sería peor que la ausencia.
- Afinar `verificar_reporte.py` contra un `.pbip` real — hoy es una heurística declarada como tal.

## 15. Instalación como plugin (v2)

FAW dejó de instalarse pegando config a mano en cada proyecto. Es un **plugin de Claude Code**: `.claude-plugin/plugin.json` declara los hooks por ruta propia, y las carpetas `skills/` y `agents/` de la raíz se auto-descubren — o sea que las 6 skills y el agente validador quedan instalados, que antes estaban escritos pero inertes.

```bash
claude --plugin-dir ~/faw          # cargarlo para una sesión (desarrollo)
claude plugin validate ~/faw       # verificar el manifest
```

Un proyecto se suma creando `.faw/` en su raíz. Sin ese directorio, todos los hooks salen sin hacer nada.

**Por qué los hooks no van en `hooks/hooks.json`, que es el default:** DAW lo midió y lo documenta — ese default lo comparten varias herramientas, y si Claude encuentra en el archivo un nombre de evento que no es suyo, **descarta el archivo entero, en silencio, e instala sin hacer cumplir nada.** Cada herramienta nombra su propio archivo.

## 16. Dónde está todo

```
~/faw/                              El repo, clonado donde prefieras (~/faw en los ejemplos)
├── .claude-plugin/plugin.json      Manifest del plugin (declara los hooks)
├── GUIA_COMPLETA.md                Este documento
├── README.md                       Presentación breve del método
├── adapters/claude/settings.snippet.json   Plantilla del hook para pegar en un proyecto
├── docs/
│   └── INSTALACION.md              Cómo engancharlo, cómo instalar el hook
├── faw/
│   ├── reglas/                     00-principios · fases · cliente · skills-microsoft
│   ├── transiciones.json           El grafo
│   ├── recibos.py                  Los recibos firmados
│   ├── hooks/pre_commit_metadata.py
│   └── contratos/                  Plantillas de tabla, modelo
├── scripts/
│   ├── estado.py                   Camina el grafo, exige recibos
│   ├── verificar_contrato.py · verificar_diff.py
│   ├── verificar_modelo.py · verificar_reporte.py
│   ├── verificar_brief.py          Compuerta brief (tier REPORTE)
│   ├── verificar_plataforma.py     Compuerta plataforma (sintaxis de Microsoft)
│   └── autoverificar.py            Canary: prueba que los verificadores no se rompieron
├── agents/faw-validador.md
└── skills/
    ├── faw-clasificar · faw-perfilar · faw-validar
    └── faw-backlog · faw-roadmap · faw-arquitectura

~/skills-for-fabric/                Clon de microsoft/skills-for-fabric (capa de plataforma, §13b)
~\.claude\agents\fabric-data-engineer.md   Wrapper local del agente de Microsoft
```

Cada proyecto que adopta FAW no lo copia: apunta a esta ruta desde su propio `CLAUDE.md` (§ver `docs/INSTALACION.md`) y agrega su propio hook local.
