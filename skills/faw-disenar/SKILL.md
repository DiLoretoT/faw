---
name: faw-disenar
description: Conduce la fase de DISEÑO — grano, clave natural, contrato de datos y las decisiones de plataforma que son caras de revertir (modo de almacenamiento, dónde se resuelve cada cálculo, dónde vive cada capa). Usar antes de construir cualquier artefacto o modelo semántico.
---

# Diseño

Esta fase decide lo que después cuesta caro cambiar. Un error de código se corrige con un commit; un error de grano o de modo de almacenamiento se corrige reconstruyendo la tabla, el modelo y todo lo que dependa de ellos.

El objetivo no es producir un documento: es que cada decisión que la solución va a arrastrar quede tomada a propósito, con su fundamento, y confirmada por el usuario antes de escribir la primera línea.

## Lo que hay que producir

1. **El grano, en una frase.** "Una fila por movimiento de caja" o "una fila por producto y día". Si la frase necesita una conjunción para ser cierta, el grano no está definido.
2. **La clave natural, verificada contra el origen.** Verificada quiere decir que se corrió la consulta que compara el total de filas contra el total de combinaciones distintas. Copiarla de una ficha técnica no es verificarla.
3. **El contrato de datos** (`faw/contratos/PLANTILLA.contrato.yml`): columnas, tipos, aserciones.
4. **Las decisiones de plataforma**, abajo.
5. **La confirmación del usuario**, que es la compuerta de salida de la fase.

## Las decisiones de plataforma

Estas decisiones aparecen en todo proyecto de Fabric y casi nunca se plantean de forma explícita: se heredan del default de un diálogo o de lo que se hizo la vez anterior. Un default que nadie eligió es una decisión que tomó la herramienta.

**La regla de esta skill: cada una de estas decisiones se plantea, se decide y se justifica, incluso cuando la respuesta parece obvia.** Se le ofrece al usuario el análisis aunque no lo haya pedido y aunque no conozca el tema, porque la consecuencia de equivocarla la paga igual.

### Modo de almacenamiento del modelo semántico

Es la decisión más cara de revertir de un modelo. Las opciones son Import, Direct Lake y DirectQuery, y la elección depende de tres cosas: el volumen de datos, con qué frecuencia cambian, y cuánta latencia tolera quien consume el reporte.

Antes de recomendar una, **leer la documentación oficial vigente** y citar la fecha de la página. Las capacidades y los límites de Direct Lake en particular cambian entre releases, así que una recomendación basada en lo que se sabía hace seis meses puede estar equivocada hoy.

Las restricciones que conviene tener presentes al plantear la decisión, y confirmar contra la documentación en cada caso:

- **Direct Lake no soporta columnas calculadas.** Todo cálculo que se pensaba resolver como columna en el modelo tiene que resolverse aguas arriba, en la tabla, o expresarse como medida.
- **La seguridad a nivel de fila u objeto sobre las tablas de origen afecta el modo.** Un modelo Direct Lake que consume tablas con esas reglas aplicadas puede degradarse a DirectQuery o directamente fallar la consulta, según por dónde acceda a los datos. Si el diseño incluye seguridad por filas, la interacción con el modo de almacenamiento se verifica **antes** de construir, no cuando el visual aparezca vacío.
- **Direct Lake tiene límites de tamaño y de estructura de los archivos** que dependen del tipo de capacidad. Un modelo que los supera vuelve a DirectQuery sin avisar de forma evidente.

Cuando el usuario no tiene criterio formado sobre esto, la skill no elige por él en silencio: explica en dos o tres frases qué implica cada opción **para este caso concreto** —no en abstracto— y recomienda una con su fundamento.

### Dónde se resuelve cada cálculo

Para cada campo derivado, decidir si se materializa aguas arriba en la tabla o se expresa como medida en el modelo. El default es aguas arriba, y las excepciones son legítimas: un cálculo que depende del contexto de filtro del usuario tiene que ser una medida. El principio 5 desarrolla el criterio.

### El resto de las decisiones que se arrastran

- **Grano de cada tabla de hechos**, y si hace falta más de uno.
- **Claves sustitutas o naturales**, y qué pasa con las filas cuya clave no resuelve.
- **Dónde viven las dimensiones compartidas** cuando hay más de un modelo que las usa.
- **Estrategia de carga**: completa o incremental. Si es incremental, cuál es la marca de agua y qué pasa cuando una corrida falla a la mitad.
- **Convención de nombres**, que es barata de fijar al principio e imposible de cambiar después.

## Cuando el diseño no está maduro para decidirse

A veces el pedido llega sin la información necesaria para cerrar el diseño: falta entender el origen, falta una definición de negocio, o hay una decisión de plataforma que depende de datos que todavía no se midieron.

En ese caso **no se avanza a fuerza de supuestos**. Se le ofrece al usuario abrir una consulta previa, que es un trabajo de tier `CONSULTA` acotado a resolver exactamente esas dudas: leer la documentación que haga falta, medir el origen, y devolver un documento con las respuestas.

Ese documento después se pasa como contexto al abrir el trabajo real:

```
python <faw>/scripts/estado.py iniciar --tier ARTEFACTO --titulo "..." \
    --contexto docs/faw/consultas/<id>.md
```

El punto de hacerlo así es que la información no se pierde entre una conversación y la otra. Al abrir el trabajo real **no se vuelve a preguntar lo que el usuario ya contestó**: se le reconfirma en una línea lo que quedó decidido y se le piden únicamente los datos nuevos que hagan falta.

## Antes de construir

La fase cierra con la confirmación del usuario, y la pregunta de cierre dice qué se va a hacer si confirma, no solo a qué fase se pasa (principio 14).

Si el artefacto tiene una skill oficial de la plataforma que gobierna su mecánica, se lee **antes** de construir, no mientras se construye. Ver [`skills-microsoft.md`](../../faw/reglas/skills-microsoft.md).
