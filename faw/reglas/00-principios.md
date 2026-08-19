# Principios — se aplican en todas las fases

Estas catorce reglas no dependen del tier ni de la fase. Si alguna entra en conflicto con una instrucción puntual, gana la regla y se avisa.

## Dónde viven y qué las hace cumplir

Este archivo es la fuente. El agente lo lee al abrir un trabajo, y el hook de contexto le recuerda en cada turno los principios que gobiernan la fase en curso, para que no dependa de haberlo leído una vez al principio.

Eso no alcanza por sí solo, y conviene ser preciso sobre por qué. Un principio puede estar respaldado de tres formas distintas, y la diferencia importa porque determina qué pasa cuando alguien no lo cumple:

| Respaldo | Qué significa | Qué pasa si se incumple |
|---|---|---|
| **Compuerta** | Un verificador lo comprueba y emite un recibo que la máquina de estados recomputa | La fase no avanza |
| **Hook** | Un programa lo intercepta antes de que la acción ocurra | La acción se deniega |
| **Lectura** | Está escrito acá y el agente lo aplica | Nada lo detiene; se detecta después, o no se detecta |

Cada principio dice cuál tiene. Los que dicen **lectura** son los que dependen del criterio del agente: eso no es un defecto que se pueda ocultar, es el límite real del método. Un principio marcado como lectura y presentado como garantía sería una compuerta prometida que no existe, que es exactamente el fallo que FAW existe para evitar.

---

## 1. Evidencia antes que declaración

*Respaldo: lectura, más el recibo de perfilado en los tiers que lo exigen.*

Todo número que aparece en un cierre de fase viene de una consulta que se puede mostrar.

- Si se midió → el número y la consulta.
- Si se estimó → la palabra **"estimado"** y de dónde sale.
- Si no se midió → **"no medido"**. No hay tercera opción.

Un número sin fuente no es un dato: es una opinión con formato de dato. En datos, el número *es* el entregable.

## 2. Validar esquema, no solo conteo

*Respaldo: compuerta `contrato` y `esquema`, verificadas por `verificar_contrato.py`.*

Una tabla nunca se da por validada con un conteo de filas. Se compara **nombre y tipo de cada columna** contra su contrato.

El modo de fallo que cierra: una tabla puede coincidir exactamente con el número de filas esperado y tener la mitad de las columnas que declara. Quien mira solo el conteo la da por buena, y el conteo era correcto.

Al cerrar cualquier escritura se reporta: filas **y** columnas.

## 3. Autorización explícita por turno para escribir en el tenant

*Respaldo: hook, sobre las escrituras que pasan por herramientas MCP. En un proyecto sin ambiente de desarrollo separado, la autorización además debe quedar por escrito antes de ejecutarse.*

Ninguna escritura en el tenant sin un OK explícito **en el mismo turno**. Incluye tablas temporales y escrituras "solo para verificar". Sin excepción por tamaño ni por intención.

Antes de pedirla se dice con precisión: qué tabla, qué operación, cuántas filas se afectan, qué se crea y qué se borra. Después se reporta qué pasó realmente.

El límite del respaldo: el hook alcanza las herramientas MCP, no el código que se ejecuta dentro de una sesión Spark. Ahí el principio vuelve a ser lectura.

## 4. El silencio es el enemigo

*Respaldo: lectura, con la parte de esquema respaldada por la compuerta `contrato`.*

Entre un artefacto que falla y uno que devuelve un número dudoso, siempre el que falla.

- Ninguna FK de Gold queda nula: va a un miembro Desconocido **visible**.
- Toda tabla lleva una aserción de clave natural que corta la ejecución ante duplicados.
- Un cambio de esquema no deseado hace fallar la escritura, no la pisa.
- Los valores que no encajan en ninguna categoría tienen su propia categoría; no se mezclan con la última.

## 5. Lo derivado se resuelve lo más aguas arriba que el diseño permita

*Respaldo: lectura. Es un criterio de diseño, no una regla mecánica.*

El default es materializar una columna derivada en Gold y no en la capa de consumo. La razón es de costo y de consistencia: lo que se calcula una vez al escribir se calcula una vez, y todos los consumidores ven el mismo valor; lo que se calcula en el modelo se recalcula por consulta y puede diferir entre reportes que definan lo mismo dos veces.

**Dónde el default no aplica**, y son casos legítimos, no excepciones a justificar:

- Un cálculo que depende del contexto de filtro del usuario **tiene que** ser una medida. Un ratio, un promedio ponderado o un acumulado no se pueden materializar como columna sin fijar de antemano el nivel de agregación.
- Una columna cuya cardinalidad haría crecer la tabla de forma desproporcionada puede convenir en el modelo, aunque sea calculable aguas arriba.
- Un cálculo que cambia seguido y no vale reprocesar la tabla entera cada vez.

Hay un dato de plataforma que sí es fijo y conviene tener presente al decidir: **Direct Lake no soporta columnas calculadas**. En un modelo Direct Lake la opción de "resolverlo en el modelo como columna" directamente no existe, así que la decisión es entre materializar aguas arriba o expresarlo como medida.

La regla operativa es que la ubicación de un cálculo se decide y se explica en el diseño, no que exista un único lugar correcto.

## 6. Afirmaciones sobre la plataforma: documentación oficial leída

*Respaldo: compuerta `plataforma` para literales de sintaxis, verificada por `verificar_plataforma.py`. Para el resto, lectura.*

Toda afirmación determinante sobre Fabric o Power BI —"no se puede X", "conviene A sobre B", límites de una feature— se respalda con documentación oficial **leída**, citando la fecha de la página.

Un resumen de buscador sirve para saber dónde mirar, no como cita. Si la documentación no lo dice explícitamente, se declara como **inferencia u observación propia**, nunca como comportamiento documentado.

## 7. Saber quién lee cada superficie

*Respaldo: hook, sobre el diff de cada commit y sobre el cuerpo de cada PR.*

Antes de escribir en cualquier lado, preguntarse quién lo lee. Detalle en [`cliente.md`](cliente.md).

Resumen: un repositorio remoto **no** es un espacio de trabajo interno. FAW trata todo repo gobernado como superficie de cliente, sin distinguir de quién es.

## 8. No pelear con el serializador

*Respaldo: lectura.*

Cuando Fabric reserializa un artefacto a su formato canónico, se acepta ese formato. Si aparece un diff que es solo formato, se comitea y se cierra el ciclo. Nunca se revierte en un PR.

Antes de aprobar un diff como "cosmético" se lo inspecciona **entero**, incluido el encabezado. Un resumen de líneas agregadas y quitadas no es prueba.

## 9. Reproducir código a mano es peligroso

*Respaldo: lectura.*

Correr un notebook reproduciéndolo en una sesión interactiva es a veces la única opción. Cuando se hace:

- se reproduce **completo**, nunca una versión abreviada;
- al terminar se imprime el esquema del resultado y se compara contra el archivo fuente;
- se declara en el cierre que fue una reproducción manual y no una corrida del artefacto real.

El fallo característico es escribir una versión recortada, olvidarse de que lo era, y validarla como si fuera la buena.

## 10. El estado "success" de un job no es evidencia

*Respaldo: lectura.*

Un pipeline o un notebook con status "Succeeded" no prueba que haya pasado algo. Un Copy activity contra una fuente vacía, un MERGE que no matcheó ninguna fila, un notebook cuya aserción de guardia nunca se disparó porque el DataFrame de entrada vino vacío: todos terminan en éxito.

- Nunca se lee el status del job como evidencia de que el trabajo se hizo.
- Se compara el delta real —filas escritas, filas afectadas— contra un mínimo esperado.
- "Succeeded" y "0 filas afectadas" al mismo tiempo es un fallo, no un éxito silencioso.

## 11. Verificar contra el ambiente real, no contra el código

*Respaldo: compuerta `metadata` sobre el diff. Para el resto de las superficies, lectura.*

El repo declara la intención; el workspace desplegado es la fuente de verificación. No se asume que coinciden sin comprobarlo.

Es la generalización de lo que la compuerta `metadata` aplica sobre el diff: un cambio que parece inocuo puede alterar configuración que nadie está mirando. El mismo patrón aparece en otras superficies:

- Una Variable Library con valores distintos por ambiente que el notebook asume iguales.
- Permisos de workspace cambiados a mano en la interfaz, sin paso por el repo.
- Un shortcut de OneLake que apunta a otro lado del que el código cree.

Antes de dar por buena una lectura del ambiente hecha de memoria o desde el código, se confirma contra el workspace real.

## 12. Una relación que publica sin error no está verificada

*Respaldo: compuerta `modelo` para la dirección y las propiedades declaradas, verificada por `verificar_modelo.py`. La prueba con datos reales es lectura.*

Que un modelo semántico publique y las queries corran no prueba que una relación entre un hecho y una dimensión quede en la dirección correcta. Al cerrar el modelado se confirma, relación por relación, que el hecho queda del lado "muchos", probando un filtro real desde la dimensión contra el conteo esperado, no solo mirando que el editor no marque error.

## 13. La fase se declara en cada respuesta

*Respaldo: el hook de contexto inyecta el recordatorio en cada turno; que la línea aparezca es lectura.*

Toda respuesta arranca con una línea de estado. Con trabajo abierto: `{TIER} — {acción} | {ticket}: {título}`. Para una consulta suelta que no toca nada: `[consulta]`.

No es decoración: es la única forma de que el usuario detecte una desviación **en el momento**, sin tener que preguntar. Sin la línea de estado, saltarse la clasificación es invisible hasta que el trabajo ya está hecho; con ella, un tier declarado en una fase que nunca se abrió salta en el segundo mensaje.

Es la regla más barata del método y la que más rápido expone que las demás no se están cumpliendo.

## 14. Ninguna pregunta de cierre sin decir qué se va a hacer

*Respaldo: lectura.*

Toda pregunta de punto de control ("¿cierro con esto?", "¿arrancamos?") va precedida de **una frase concreta de qué acción sigue** si el usuario dice que sí. No alcanza con nombrar la fase siguiente: eso dice *dónde*, no *qué*.

Mal: *"¿Cierro con esto y sigo a PERFILADO?"*
Bien: *"Voy a perfilar el origen: correr `count(*)` contra `count(distinct)` sobre la clave candidata y medir nulos por columna. ¿Sigo?"*

Sin la frase de acción, el usuario aprueba una fase en abstracto y descubre qué hizo el agente recién cuando ya está hecho. Con la frase, la aprobación es sobre algo concreto y el desvío se nota antes de que ocurra.

Cualquier skill que cierre con una pregunta antepone esa frase. Si la acción real depende de lo que se encuentre, se dice así: no se inventa una frase genérica para cumplir la forma.
