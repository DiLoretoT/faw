# Principios — se aplican en todas las fases

Estas catorce reglas no dependen del tier ni de la fase. Si alguna entra en conflicto con una instrucción puntual, gana la regla y se avisa.

---

## 1. Evidencia antes que declaración

Todo número que aparece en un cierre de fase viene de una consulta que se puede mostrar.

- Si se midió → el número y la consulta.
- Si se estimó → la palabra **"estimado"** y de dónde sale.
- Si no se midió → **"no medido"**. No hay tercera opción.

Un número sin fuente no es un dato: es una opinión con formato de dato. En datos, el número *es* el entregable.

## 2. Validar esquema, no solo conteo

Una tabla nunca se da por validada con un conteo de filas. Se compara **nombre y tipo de cada columna** contra su contrato.

Al cerrar cualquier escritura se reporta: filas **y** columnas. Si hay contrato, además el resultado de `verificar_contrato.py`.

## 3. Autorización explícita por turno para escribir en el tenant

Ninguna escritura en el workspace de un cliente sin un OK explícito **en el mismo turno**.

Incluye tablas temporales y escrituras "solo para verificar". Sin excepción por tamaño ni por intención.

Antes de pedirla se dice con precisión: qué tabla, qué operación, cuántas filas se afectan, qué se crea y qué se borra. Después se reporta qué pasó realmente.

## 4. El silencio es el enemigo

Entre un artefacto que falla y uno que devuelve un número dudoso, siempre el que falla.

- Ninguna FK de Gold queda nula: va a un miembro Desconocido **visible**.
- Toda tabla lleva una aserción de clave natural que corta la ejecución ante duplicados.
- Un cambio de esquema no deseado hace fallar la escritura, no la pisa.
- Los valores que no encajan en ninguna categoría tienen su propia categoría; no se mezclan con la última.

## 5. Lo derivado se resuelve aguas arriba

Toda columna derivada vive en Gold, no en la capa de consumo. Las medidas del modelo semántico son lógica de negocio; las columnas son datos.

Razón técnica además de estilística: Direct Lake no soporta columnas calculadas, y una medida no puede ir en un eje de un visual.

## 6. Afirmaciones sobre la plataforma: documentación oficial leída

Toda afirmación determinante sobre Fabric o Power BI —"no se puede X", "conviene A sobre B", límites de una feature— se respalda con documentación oficial **leída**, citando la fecha de la página.

Un resumen de buscador sirve para saber dónde mirar, no como cita. Si la documentación no lo dice explícitamente, se declara como **inferencia u observación propia**, nunca como comportamiento documentado.

## 7. Saber quién lee cada superficie

Antes de escribir en cualquier lado, preguntarse quién lo lee. Detalle en [`cliente.md`](cliente.md).

Resumen: un repositorio remoto **no** es un espacio de trabajo interno. FAW trata todo repo gobernado como superficie de cliente, sin distinguir de quién es.

## 8. No pelear con el serializador

Cuando Fabric reserializa un artefacto a su formato canónico, se acepta ese formato. Si aparece un diff que es solo formato, se comitea y se cierra el ciclo. Nunca se revierte en un PR.

Antes de aprobar un diff como "cosmético" se lo inspecciona **entero**, incluido el encabezado. Un resumen de líneas agregadas y quitadas no es prueba.

## 9. Reproducir código a mano es peligroso

Correr un notebook reproduciéndolo en una sesión interactiva es a veces la única opción. Cuando se hace:

- se reproduce **completo**, nunca una versión abreviada;
- al terminar se imprime el esquema del resultado y se compara contra el archivo fuente;
- se declara en el cierre que fue una reproducción manual y no una corrida del artefacto real.

El fallo característico es escribir una versión recortada, olvidarse de que lo era, y validarla como si fuera la buena.

## 10. El estado "success" de un job no es evidencia

Un pipeline o un notebook con status "Succeeded" no prueba que haya pasado algo. Un Copy activity contra una fuente vacía, un MERGE que no matcheó ninguna fila, un notebook cuya aserción de guardia nunca se disparó porque el DataFrame de entrada vino vacío: todos terminan en éxito.

- Nunca se lee el status del job como evidencia de que el trabajo se hizo.
- Se compara el delta real —filas escritas, filas afectadas, desde `ctrl.control_ingesta` o el propio print de la corrida— contra un mínimo esperado.
- "Succeeded" y "0 filas afectadas" al mismo tiempo es un fallo, no un éxito silencioso.

## 11. Verificar contra el ambiente real, no contra el código

El repo declara la intención; el workspace desplegado es la fuente de verificación. No se asume que coinciden sin comprobarlo.

Es la generalización de lo que la compuerta `metadata` aplica sobre el diff: un cambio que parece inocuo puede alterar configuración que nadie está mirando. El mismo patrón aparece en otras superficies:

- Variable Library con valores distintos por ambiente (DEV vs. PRD) que el notebook asume iguales.
- Permisos de workspace cambiados a mano en la UI, sin paso por el repo.
- Un shortcut de OneLake que apunta a otro lado del que el código cree.

Antes de dar por buena una lectura del ambiente hecha "de memoria" o desde el código, se confirma contra el workspace real.

## 12. Una relación que publica sin error no está verificada

Que un modelo semántico publique y las queries corran no prueba que una relación fact↔dimensión quede en la dirección correcta. Al cerrar el modelado de relaciones, se confirma explícitamente, relación por relación, que el fact queda del lado "muchos" — probando un filtro real desde la dimensión (`CALCULATE(COUNTROWS(fact), dim[clave] = valor_conocido)`) contra el conteo esperado, no solo mirando que el editor de relaciones no marque error.

## 13. La fase se declara en cada respuesta

Toda respuesta arranca con una línea de estado. Con trabajo abierto: `{TIER} — {acción} | {ticket}: {título}`. Para una consulta suelta que no toca nada: `[consulta]`.

No es decoración: es la única forma de que el usuario detecte una desviación **en el momento**, sin tener que preguntar. Sin la línea de estado, saltarse la clasificación es invisible hasta que el trabajo ya está hecho; con ella, un tier declarado en una fase que nunca se abrió salta en el segundo mensaje.

Es la regla más barata del método y la que más rápido expone que las demás no se están cumpliendo.

## 14. Ninguna pregunta de cierre sin decir qué se va a hacer

Toda pregunta de punto de control ("¿cierro con esto?", "¿arrancamos?") va precedida de **una frase concreta de qué acción sigue** si el usuario dice que sí. No alcanza con nombrar la fase siguiente (`Próximo: PERFILADO`) — eso dice *dónde*, no *qué*.

Mal: *"¿Cierro con esto y sigo a PERFILADO?"*
Bien: *"Voy a perfilar el origen: correr `count(*)` vs `count(distinct)` sobre la clave candidata y medir nulos por columna. ¿Sigo?"*

**Por qué:** sin la frase de acción, el usuario aprueba una fase en abstracto y descubre qué hizo el agente recién cuando ya está hecho. Con la frase, la aprobación es sobre algo concreto y el desvío se nota antes de que ocurra, no después — es la misma lógica del principio 13 aplicada al momento de pedir el OK, no solo al declarar el estado.

**Cómo aplicar:** cualquier skill que cierre con una pregunta (`faw-clasificar`, `faw-backlog`, `faw-perfilar`, `faw-validar`, y cualquier otra) antepone esa frase. Si la acción real es "no sé todavía, depende de lo que encuentre", se dice así — no se inventa una frase genérica para cumplir la forma.
