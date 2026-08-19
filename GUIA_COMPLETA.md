# FAW — Guía completa

Documento de referencia del método. Explica qué problema resuelve, cómo está construido y cómo se opera. Las reglas que el agente carga en cada turno viven aparte, en [`faw/reglas/`](faw/reglas/).

---

## 1. El problema

En desarrollo de software el artefacto es código y el fallo es ruidoso: algo no compila, un test se pone en rojo, una excepción interrumpe la ejecución. El trabajo de calidad consiste en gran medida en reaccionar a señales que el sistema emite solo.

En una plataforma de datos el artefacto es una tabla, y el fallo característico no emite ninguna señal. Es un número creíble y falso. Cuatro formas concretas en que ocurre:

- Una dimensión se publica con once de las veintitrés columnas que declara su contrato. La validación miró que el total de filas coincidiera, y coincidía. El conteo era correcto; la tabla no.
- Tres relaciones de un modelo semántico apuntan a la misma columna del hecho, porque alguien aceptó el valor propuesto por un diálogo tres veces seguidas. El modelo publica sin error y devuelve totales plausibles.
- Un commit descrito como "solo formato" borra además la asignación de lakehouse por defecto de varios notebooks. El diff mostrado en pantalla no llegaba hasta el encabezado del archivo.
- Las claves foráneas de fecha quedan nulas. Las partidas afectadas desaparecen del total en cuanto alguien filtra por fecha, sin ningún mensaje de error.

Ninguno de los cuatro lo detecta un test unitario, un analizador estático o una revisión de código. Los cuatro se detectan midiendo contra datos reales, y solo si alguien se acuerda de medir.

FAW existe para que esa medición no dependa de que alguien se acuerde. Cada regla del método cierra una vía concreta por la que un dato incorrecto llega a producción sin hacer ruido. Una regla que no se puede atar a un modo de fallo específico no pertenece al método.

La idea que ordena el resto: **evidencia antes que declaración**. Un número sin la consulta que lo produjo no es un dato, es una opinión con formato de dato.

---

## 2. Cómo está construido

El método tiene tres capas, y la diferencia entre ellas determina qué pasa cuando algo no se cumple. Entender esa distinción es entender FAW.

**Las reglas** son texto que el agente lee. Viven en `faw/reglas/` y describen qué hacer en cada fase, qué principios rigen siempre, y qué contenido puede llegar a cada superficie. Su fuerza depende enteramente de que el agente las lea y las aplique.

**Las compuertas** son verificadores que comprueban un hecho concreto y emiten un recibo firmado. La máquina de estados recomputa ese recibo antes de permitir un avance de fase, así que una compuerta no satisfecha detiene el trabajo. Un contrato de datos que no coincide con la tabla real no es una advertencia: es una fase que no avanza.

**Los hooks** son programas que se ejecutan antes de una acción y pueden denegarla. Corren por fuera del modelo, así que no dependen de que el agente decida invocarlos. Un intento de editar un archivo sin haber clasificado el trabajo se deniega antes de que el archivo se toque.

La razón de tener las tres es que cubren superficies distintas. Un hook puede impedir una escritura pero no puede saber si un número es correcto. Una compuerta puede verificar un esquema pero solo cuando alguien la corre. Una regla escrita puede describir criterio, que es lo que ninguna de las otras dos hace.

Lo que el método no hace es fingir que las tres son equivalentes. Cada compuerta declara qué fuerza tiene, y cada principio dice si lo respalda una compuerta, un hook o solamente su lectura. Una compuerta que se presenta como más fuerte de lo que es convierte a las demás en sugerencias.

---

## 3. Las siete clasificaciones

Lo primero que ocurre con cualquier pedido es que se le asigna un tier. El tier determina cuánto proceso paga ese trabajo, y existe para que un ajuste de tres líneas no cueste lo mismo que un modelo semántico nuevo.

| Tier | Qué es | Recorrido |
|---|---|---|
| **CONSULTA** | Una pregunta que no toca nada | No entra al grafo |
| **EXPLORACIÓN** | Entender algo sin modificarlo | Clasificación, perfilado, documento |
| **CAMBIO-MENOR** | Ajuste acotado | Clasificación, construcción, publicación |
| **ARTEFACTO** | Tabla, notebook o pipeline | Las seis fases |
| **MODELO** | Modelo semántico | Las seis, con verificación por API |
| **REPORTE** | Reporte de Power BI | Brief acordado, construcción, publicación |
| **INCIDENTE** | Algo roto | Carril rápido con diagnóstico medido |

`MODELO` y `REPORTE` están separados porque lo que se puede verificar por máquina es distinto en cada uno. En un modelo semántico las relaciones, el modo de almacenamiento y las propiedades de columna se consultan por API y se comparan contra lo declarado. En un reporte, la disposición de los visuales y la elección de cada uno no son verificables así, y el desarrollo es iterativo por naturaleza. Cobrarle a un reporte las compuertas del modelo produciría una compuerta imposible de satisfacer honestamente, y esas no deben existir.

`CAMBIO-MENOR` tiene un guardarraíl explícito: si el cambio toca esquema, lógica de negocio o capa de consumo, o supera unas treinta líneas, se reclasifica a `ARTEFACTO`. No queda a criterio del momento.

`CONSULTA` no entra a la máquina de estados. No abre ticket ni toca el archivo de estado. Meterla adentro sería la clase de ceremonia que hace abandonar un método.

---

## 4. Las fases y el grafo

`faw/transiciones.json` define un grafo dirigido. Los nodos son las fases más un estado inicial; las aristas son los movimientos permitidos; cada arista puede exigir compuertas para cruzarse.

Que sea un grafo y no una lista de reglas tiene una consecuencia práctica: desde construcción solo se puede ir a validación, nunca saltar directamente a publicación. El salto no está prohibido por una advertencia, no existe como arista.

```
ARTEFACTO / MODELO:
  CLASIFICACIÓN → PERFILADO → DISEÑO → CONSTRUCCIÓN → VALIDACIÓN → PUBLICACIÓN → IDLE
       ▲(1)                     ▲(2)                    │   ▲(3)
       └── confirmación ────────┘               si falla└───┘ vuelve a CONSTRUCCIÓN

CAMBIO-MENOR:
  CLASIFICACIÓN ─────────────────► CONSTRUCCIÓN ──────► PUBLICACIÓN → IDLE

REPORTE:
  CLASIFICACIÓN ──brief──► CONSTRUCCIÓN ──────────────► PUBLICACIÓN → IDLE
```

Los tiers son caminos distintos sobre el mismo grafo, no grafos separados. `scripts/estado.py` recorre ese grafo: comprueba en qué nodo está el trabajo, si la arista pedida existe para el tier activo, y si sus compuertas se satisfacen. Cuando algo de eso falla, rechaza la transición.

### Qué hace cada fase

**Clasificación.** Reformular el pedido en una frase, mirar el estado real del repositorio, asignar tier y definir explícitamente qué queda afuera. No se construye nada. Cierra con la confirmación del usuario.

**Perfilado.** Medir el origen. Cada número que se reporte viene acompañado de la consulta que lo produjo, y la clave natural se prueba consultando la tabla en lugar de copiarla de una ficha técnica. Es una fase de solo lectura, y el hook de escritura la hace cumplir: durante el perfilado se deniega cualquier edición que no sea el propio recibo.

**Diseño.** Grano en una frase, clave natural verificada, contrato de datos, y las decisiones de plataforma que después son caras de revertir. Cierra con confirmación del usuario antes de construir.

**Construcción.** Se implementa con las validaciones dentro del artefacto, no en un script aparte, para que corran en cada ejecución futura y no solo la primera vez. Se reporta filas y columnas, nunca filas solamente.

**Validación.** La ejecuta un agente que no construyó, con la instrucción de refutar y no de confirmar. Si falla, el trabajo vuelve a construcción: no se parcha en esta fase, porque el parche lo escribiría quien está validando y ya no quedaría nadie mirando desde afuera.

**Publicación.** Verificar el diff completo, commit, pull request, sincronizar el ambiente y comprobar el estado posterior al despliegue.

---

## 5. Los puntos de control

El proceso se detiene a esperar al usuario exactamente en tres momentos, y son pocos a propósito: un método que pregunta todo el tiempo entrena a que le respondan que sí sin leer.

1. **Después de clasificar**, antes de tocar nada: se acuerda tier y alcance.
2. **Después de diseñar**, antes de construir: se acuerda el grano, la clave y las decisiones de plataforma. Es donde una decisión equivocada cuesta más barato.
3. **Después de validar**, antes de publicar: se acuerda el veredicto.

Toda pregunta de cierre dice qué se va a hacer si el usuario confirma, no solo a qué fase se pasa. "¿Sigo a perfilado?" hace aprobar una fase en abstracto; "voy a comparar el total de filas contra el total de claves distintas y medir nulos por columna, ¿sigo?" hace aprobar algo concreto, y permite notar el desvío antes de que ocurra.

---

## 6. Las compuertas y su fuerza

Cada compuerta declara qué la respalda. La escala es honesta porque de otro modo no serviría para nada:

| Fuerza | Qué la respalda | Cómo se le puede mentir |
|---|---|---|
| **máquina** | Un script comprueba el hecho y emite un recibo que se recomputa | No se puede sin modificar el verificador |
| **recibo** | Existe un documento con contenido suficiente | Con un archivo de relleno |
| **declaración** | El agente afirma que se cumplió | Diciéndolo |

Las principales:

| Compuerta | Qué verifica | Fuerza |
|---|---|---|
| `contrato` / `esquema` | Cada columna de la tabla real contra el contrato declarado | máquina |
| `modelo` | Relaciones, modo de almacenamiento y propiedades del modelo semántico | máquina |
| `metadata` | Que el diff no altere configuración protegida sin declararlo | máquina |
| `plataforma` | Que los literales de sintaxis de la plataforma tengan precedente o resuelvan | máquina |
| `git-limpio` | Que no queden cambios sin comitear al cerrar | máquina |
| `brief` | Que el brief del reporte tenga contenido y no sea la plantilla | máquina |
| `perfil` | Que exista el recibo del perfilado y corresponda al ticket en curso | recibo |
| `confirmacion_usuario` | Que el usuario haya dado el OK | declaración |
| `autorizacion` | Que exista permiso para escribir en la plataforma | declaración, o hook |

### Los recibos

Un verificador que pasa emite un recibo con el hash de lo que verificó. La máquina de estados recomputa esos hashes antes de permitir el avance, así que un recibo emitido sobre una versión anterior del archivo ya no vale. Sin esto, "ya lo verifiqué" sería una afirmación sobre el pasado imposible de comprobar.

Las compuertas que trabajan tabla por tabla emiten un recibo por tabla. Cuando un ticket toca varias, el alcance se declara al mover de fase y la compuerta exige el recibo de cada una. Sin esa declaración, un ticket de nueve tablas podría cerrar la fase habiendo verificado solamente la última.

---

## 7. El perfil del proyecto

Hay decisiones de infraestructura que el método no puede conocer y no debe suponer: dónde viven los tickets, si existe un ambiente de desarrollo separado del productivo, si se ejecuta código contra la plataforma. Escribir esas respuestas dentro del método lo volvería correcto para un proyecto e incorrecto para todos los demás.

El perfil las declara en **`faw.json`**, en la raíz del repositorio de trabajo, y **se versiona**. Son reglas de proceso del equipo: tienen que viajar con el repositorio, revisarse en un pull request y ser iguales para todos. Un perfil que vive en una sola máquina produce dos personas trabajando bajo reglas distintas sin que nada lo detecte.

```json
{
  "tickets": { "sistema": "interno" },
  "ambientes": { "dev": false, "prd": true, "promocion": "manual" },
  "canal": { "livy": false, "tabla_control": null }
}
```

Todo es opcional. Lo que importa es cómo se resuelve lo que falta.

### Los valores por defecto son los estrictos

Un dato ausente se resuelve por la opción que más control pide, nunca por la que más permite. Sin declaración de ambientes, el método asume que hay uno solo y que es productivo, y entonces cada escritura contra la plataforma exige que el motivo quede escrito antes de ejecutarse.

La asimetría del error lo justifica: un valor estricto de más cuesta una autorización que el usuario iba a dar igual; uno permisivo de más escribe en producción sin preguntar.

Ese default no es pesimismo. Microsoft documenta el despliegue sobre un único workspace como un patrón válido y soportado para organizaciones chicas, y en ese patrón los deployment pipelines no existen porque requieren varios workspaces en la misma capacidad. Un proyecto sin ambiente de desarrollo separado es un caso normal.

### Cada clave tiene consecuencia

Una clave que solo produjera un texto distinto no estaría en el archivo. `ambientes.dev` decide si la autorización para escribir es conversada o tiene que quedar por escrito antes de ejecutarse. `tickets.sistema` decide de dónde sale el identificador del trabajo y si hay un backlog externo que consultar.

### Lo que no va acá

Nombres de personas, identificadores de otros proyectos y rutas locales van en `.faw/config.json`, que no se versiona. Esa separación existe para no tener que elegir entre publicar nombres o esconder reglas.

---

## 8. Los tickets

El método necesita un identificador de trabajo para nombrar sus recibos y para que la pregunta "en qué quedamos" tenga una respuesta que sobreviva cerrar la sesión. Ese identificador suele venir de un gestor externo, pero exigir uno convertiría una herramienta de gestión en requisito de instalación.

Hay tres situaciones y las tres funcionan igual de bien:

**El proyecto usa un gestor con servidor MCP conectado.** El agente consulta el backlog y actualiza los tickets directamente. El identificador sale de ahí.

**El proyecto usa un gestor sin MCP**, o con la conexión deshabilitada a propósito. El identificador sigue saliendo de ahí, pero lo informa el usuario y él opera su herramienta. El método no inventa el estado del backlog ni asume que un ticket existe.

**El proyecto no usa ningún gestor.** FAW lleva el registro en `docs/faw/tickets/`, genera identificadores correlativos y crea el archivo del ticket al abrir el trabajo. El historial lo aporta git, que es justamente lo que un gestor externo ofrece y un archivo suelto no: rastro de cómo cambió el alcance.

Los tickets del registro interno se versionan y **pasan por la compuerta de superficie**, a diferencia del resto de los artefactos del método. Un ticket contiene por naturaleza preguntas abiertas y tareas asignadas a personas, que es exactamente el contenido que no debe llegar a un repositorio que lee un tercero.

---

## 9. El canal de cambio

La pregunta cotidiana es por dónde va cada modificación: pull request, ejecución interactiva contra la plataforma, o la interfaz del producto. El criterio que la responde: **el canal lo decide dónde tiene que quedar el registro.**

| Qué | Canal | Autorización | Registro |
|---|---|---|---|
| Notebook, código de pipeline, contrato, documentación | Git y pull request | Al mergear | El commit |
| Leer datos, perfilar, diagnosticar | Consulta directa | Ninguna, es lectura | El recibo de perfilado |
| Escribir o borrar una tabla | Ejecución contra la plataforma | Explícita, con tabla, operación y filas | El recibo, y la tabla de control si existe |
| Canvas de pipeline, permisos, shortcuts | Interfaz del producto | Al comitear | El commit del ambiente |
| Modelo semántico, reporte | Interfaz o herramienta de escritorio | Al comitear | El commit y su verificador |
| Cualquier cosa en producción | El mecanismo de promoción declarado | Explícita, siempre | El historial del despliegue |

Dos reglas se desprenden. La primera: toda escritura hecha por ejecución directa tiene que ser **regenerable desde un artefacto versionado**. Si la lógica que la produjo existió solamente dentro de una sesión ya cerrada, eso no es un cambio, es un accidente que nadie puede reproducir. La segunda: git es la fuente de verdad de todo lo serializable, y el ambiente desplegado es destino, no lugar de edición.

### Lo que sí se puede bloquear, y lo que no

Las escrituras que pasan por herramientas de un servidor MCP **sí** están cubiertas. Esas herramientas se presentan a los hooks igual que cualquier otra, con un nombre de la forma `mcp__servidor__herramienta`, así que un hook las intercepta antes de que se ejecuten. El hook distingue lectura de escritura y, ante la duda, clasifica como escritura: equivocarse hacia el lado estricto cuesta una autorización innecesaria; hacia el otro, deja pasar una escritura sin control.

Esto importa más de lo que parece porque sin ello las fases gobernaban el código y no el dato. Se podía estar en perfilado, que es de solo lectura por definición, y escribir en la plataforma sin que nada lo notara.

La documentación de Microsoft sobre sus servidores MCP advierte que un cliente autónomo o mal configurado puede ejecutar operaciones destructivas, y que los mecanismos para impedirlo no están estandarizados en la especificación. Esa es la razón de poner la salvaguarda en el orquestador en lugar de confiar en el servidor.

**Lo que no se puede bloquear**, dicho sin adornos: el código arbitrario que corre dentro de una sesión Spark, y los archivos escritos desde la terminal con redirección o documentos embebidos. Ningún hook puede inspeccionar eso antes de que ocurra. Ahí el método detecta, no previene, y prometer lo contrario sería mentir sobre una compuerta.

---

## 10. Superficie de cliente

Antes de escribir en cualquier lado: quién lo lee.

FAW no distingue repositorios propios de repositorios de cliente. Todo repositorio gobernado se trata como superficie que lee un tercero, y cada commit y cada pull request se escriben en consecuencia. La distinción no existe a propósito: es una decisión tomada una sola vez, que elimina la posibilidad de equivocarla proyecto por proyecto.

El modo de fallo que cierra: un repositorio remoto se siente espacio de trabajo interno y no lo es. Razonamiento de diseño, hallazgos abiertos y tareas asignadas a personas terminan publicados donde los lee quien no debería, sin que nada los revise.

Lo que nunca va: hablar del cliente en tercera persona, asignar tareas a su gente, hallazgos de negocio sin cerrar, alternativas descartadas con su razonamiento completo, metodología interna, y atribución de asistencia de IA. Lo que sí va en un pull request: qué cambió, una línea de fundamento por decisión no obvia, los números de la validación, y la nota de despliegue si hace falta un paso manual.

Lo específico de cada proyecto —nombres de personas, identificadores de otros proyectos— se declara en `.faw/config.json` y la compuerta frena el commit o el pull request que lo contenga. Detalle en [`faw/reglas/cliente.md`](faw/reglas/cliente.md).

---

## 11. Los principios

Catorce reglas que no dependen del tier ni de la fase. Viven en [`faw/reglas/00-principios.md`](faw/reglas/00-principios.md), que es el archivo que el agente lee al abrir un trabajo, y el hook de contexto le recuerda en cada turno los que gobiernan la fase en curso.

Cada principio declara qué lo respalda: una compuerta, un hook, o solamente su lectura. Los que dependen de la lectura son los que dependen del criterio del agente, y eso está marcado en vez de disimulado. Un principio presentado como garantía sin nada que lo haga cumplir sería exactamente el fallo que el método existe para evitar.

Los catorce, en una línea cada uno: evidencia antes que declaración; validar esquema y no solo conteo; autorización explícita por turno para escribir; entre fallar y devolver un número dudoso, fallar; resolver lo derivado lo más aguas arriba que el diseño permita; afirmaciones sobre la plataforma con documentación leída y fechada; saber quién lee cada superficie; no pelear con el serializador; reproducir código a mano es peligroso; el estado "success" de un job no es evidencia; verificar contra el ambiente real y no contra el código; una relación que publica sin error no está verificada; la fase se declara en cada respuesta; ninguna pregunta de cierre sin decir qué se va a hacer.

---

## 12. Las decisiones de plataforma

Hay decisiones que aparecen en todo proyecto de Fabric y que casi nunca se plantean de forma explícita: se heredan del valor por defecto de un diálogo o de lo que se hizo la vez anterior. Un default que nadie eligió es una decisión que tomó la herramienta.

La fase de diseño obliga a plantearlas, decidirlas y justificarlas, **incluso cuando el usuario no pregunta y aunque no conozca el tema**, porque la consecuencia de equivocarlas la paga igual. La más cara de revertir es el modo de almacenamiento del modelo semántico, donde la elección entre importación, Direct Lake y consulta directa depende del volumen, de la frecuencia de cambio y de la latencia que tolera quien consume.

El método no reemplaza la documentación oficial en esto, y no debería: las capacidades y los límites cambian entre releases, y una recomendación basada en lo que se sabía hace seis meses puede estar equivocada hoy. Lo que el método aporta es la obligación de plantear la decisión y de respaldarla con documentación leída y fechada. Detalle en la skill de diseño.

Cuando el diseño no tiene la información necesaria para cerrarse, no se avanza a fuerza de supuestos: se abre una consulta acotada a resolver esas dudas, y su resultado se pasa como contexto al abrir el trabajo real. Al abrirlo no se vuelve a preguntar lo que el usuario ya contestó.

---

## 13. La capa de plataforma

FAW no enseña a escribir un Eventstream ni cuál API despliega un modelo semántico, a propósito: ese conocimiento cambia con cada release y mantenerlo a mano garantiza que envejezca mal sin que nadie lo note.

Esa capa la mantiene Microsoft en [`microsoft/skills-for-fabric`](https://github.com/microsoft/skills-for-fabric). Las dos capas se complementan porque resuelven cosas distintas: ese repositorio se declara enfocado en la autoría de artefactos y sin compuertas formales ni contratos de datos, que es precisamente lo que aporta FAW.

Dos reglas gobiernan la convivencia. FAW manda en proceso y esas skills mandan en mecánica: si una dice "desplegar directo al ambiente" y FAW dice "por pull request", gana FAW, porque esas skills no conocen el canal de cambio del proyecto. Y ninguna operación de escritura que propongan exime del OK del turno: la skill dice cómo, el permiso lo da el usuario.

Detalle en [`faw/reglas/skills-microsoft.md`](faw/reglas/skills-microsoft.md).

---

## 14. Los instrumentos

**Skills** (`skills/faw-*`): instrucciones que se cargan al arrancar una fase o una tarea. `faw-configurar` define el perfil del proyecto. `faw-clasificar`, `faw-perfilar`, `faw-disenar` y `faw-validar` conducen fases. `faw-backlog` y `faw-roadmap` responden qué sigue y hacia dónde se va. `faw-arquitectura` audita las decisiones caras de revertir. No obligan a nada por sí solas.

**Verificadores** (`scripts/`): cada uno comprueba un hecho y emite un recibo.

| Verificador | Qué atrapa |
|---|---|
| `verificar_contrato.py` | Una tabla publicada con menos columnas de las que declara |
| `verificar_modelo.py` | Relaciones invertidas, modo de almacenamiento equivocado |
| `verificar_diff.py` | El commit "de formato" que además borra configuración |
| `verificar_plataforma.py` | Un literal de sintaxis inventado por analogía |
| `verificar_brief.py` | Un reporte construido sin acordar objetivo y audiencia |
| `verificar_reporte.py` | El filtro de desarrollo olvidado y persistido |
| `autoverificar.py` | Que los verificadores no se hayan roto con el tiempo |

`autoverificar.py` merece una explicación aparte porque no verifica el proyecto: verifica a los verificadores. Arma en un directorio temporal un caso que debe pasar y uno con un defecto conocido que debe fallar, y comprueba que cada uno se comporte como corresponde. Sin eso, una expresión regular modificada por accidente o una condición invertida dejarían una compuerta aprobando todo, y se vería igual que una compuerta funcionando.

**Hooks** (`faw/hooks/`): inyección del estado en cada turno, denegación de escrituras fuera de fase, revisión del diff y del cuerpo del pull request antes de que existan, y la compuerta sobre las escrituras por MCP.

**La máquina de estados** (`scripts/estado.py`): recorre el grafo, exige los recibos y registra cada transición en `.faw/estado.jsonl`, un log solo-append. No es auditoría formal: es que la respuesta a "en qué quedamos" no dependa de la memoria de nadie dos semanas después.

---

## 15. Un ciclo completo

Los comandos asumen que FAW está instalado en `<faw>`; cuando está instalado como plugin, cualquier mensaje de una compuerta imprime la ruta exacta.

```bash
# CLASIFICACIÓN — se acuerda tier y alcance, y recién después se registra.
# Sin gestor externo, el identificador lo genera FAW y crea el archivo del ticket.
python <faw>/scripts/estado.py iniciar --tier ARTEFACTO --titulo "fact_movimiento" \
    --artefacto notebook
# Antes de esto, el hook de escritura deniega cualquier edición.

# PERFILADO — solo lectura. El recibo va en docs/faw/<ticket>/perfilado.md,
# con cada número acompañado de la consulta que lo produjo.
python <faw>/scripts/estado.py mover --a PERFILADO \
    --compuerta confirmacion_usuario="OK al tier y alcance"

# DISEÑO — grano, clave, contrato y decisiones de plataforma.
python <faw>/scripts/estado.py mover --a DISENO \
    --compuerta perfil=docs/faw/T-001/perfilado.md
python <faw>/scripts/verificar_contrato.py --solo-sintaxis \
    --contrato contratos/gold.fact_movimiento.yml

# CONSTRUCCIÓN — con la skill oficial de la plataforma leída antes de escribir.
python <faw>/scripts/estado.py mover --a CONSTRUCCION \
    --compuerta confirmacion_usuario="OK al diseño y al contrato"
# Si el ticket toca varias tablas, se declara el alcance:
#   --compuerta tablas=gold.fact_movimiento,gold.dim_cuenta

# VALIDACIÓN — la ejecuta el agente validador, que no construyó.
python <faw>/scripts/estado.py mover --a VALIDACION \
    --compuerta aserciones="clave natural sin duplicados, esquema OK, 2705 filas" \
    --compuerta autorizacion="OK explícito para escribir gold.fact_movimiento"

# PUBLICACIÓN — los hooks revisan el commit y el pull request antes de que existan.
python <faw>/scripts/estado.py mover --a PUBLICACION \
    --compuerta confirmacion_usuario="OK al veredicto del validador"

# CIERRE — exige que no queden cambios sin comitear.
python <faw>/scripts/estado.py mover --a IDLE
```

Pausar y retomar es lo que hace que el método sobreviva cerrar la sesión:

```bash
python <faw>/scripts/estado.py pausar --motivo "falta confirmación del negocio"
python <faw>/scripts/estado.py reanudar
python <faw>/scripts/estado.py estado
```

---

## 16. Cómo saber que está funcionando

Tres señales, de la más rápida a la más profunda.

**La línea de estado.** Si una respuesta no arranca declarando fase y ticket, el principio 13 no se está cumpliendo, y ese es el síntoma más temprano de que tampoco se cumplen los demás.

**La inyección por turno.** Se comprueba pasándole al hook de contexto un directorio de proyecto y viendo si devuelve JSON. Si no devuelve nada, el proyecto no tiene `.faw/` o el hook está fallando.

**Que los hooks bloqueen de verdad.** La prueba es intentar la acción prohibida y ver la denegación: pedir una escritura sin trabajo clasificado, o crear un pull request con un cuerpo largo.

El modo de falla que más importa vigilar: un hook que se rompe termina con un código de salida distinto de cero, y eso se trata como *no bloqueante*. Un hook roto se ve igual que un hook que aprueba. Por eso los hooks se prueban ejecutándolos, no leyéndolos, y por eso todos fuerzan la codificación de su salida: en Windows la salida estándar usa cp1252 por defecto y un carácter fuera de ese conjunto alcanza para que el proceso termine mal.

---

## 17. Lo que falta, a propósito

- Un criterio de promoción entre ambientes. No hay uno definido, y escribir uno inventado sería peor que la ausencia.
- Cobertura de las corridas que escriben desde una sesión Spark: ahí el método detecta y no previene.
- Un tier de orquestación de pipelines. Las dependencias, las marcas de agua y la concurrencia son su propia clase de fallo, y conviene diseñarlo después de tener pipelines reales bajo el método.
- Verificación de la interacción entre seguridad por filas y modo de almacenamiento, que hoy es una regla escrita y no una compuerta.

---

## 18. Instalación

```bash
claude plugin marketplace add DiLoretoT/faw
claude plugin install faw@faw
```

Quedan registrados los hooks, las skills y el agente validador. Un proyecto se suma creando `.faw/` en su raíz; sin ese directorio, todos los hooks salen sin hacer nada, así que instalar el plugin no impone el método a proyectos que no lo pidieron.

Después conviene correr `/faw-configurar` una vez, para que el método deje de suponer lo que puede preguntar. Detalle en [`docs/INSTALACION.md`](docs/INSTALACION.md).
