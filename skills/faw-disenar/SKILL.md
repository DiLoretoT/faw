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

## Las decisiones que se toman solas si nadie las mira

Todo artefacto que se construye deja decisiones de arquitectura tomadas, se hayan discutido o no. Cuando no se discuten, las toma el valor por defecto de un diálogo, la costumbre del proyecto anterior, o el primer camino que apareció. Un default que nadie eligió sigue siendo una decisión, con la diferencia de que nadie puede explicar por qué se tomó ni qué se descartó.

**Lo que esta skill obliga a hacer no es decidir una lista fija de temas.** Es preguntarse, antes de construir, qué decisiones va a dejar fijadas este trabajo, y poner sobre la mesa las que el usuario todavía no discutió. Después él decide si quiere revisarlas o seguir con el default: lo que no puede pasar es que se entere de la decisión cuando ya es cara de revertir.

El criterio para saber cuáles sacar a la luz: **si cambiarla dentro de tres meses obligaría a reconstruir algo, se plantea ahora.** Si es reversible con un commit, no hace falta.

La conversación se ofrece aunque el usuario no la haya pedido y aunque no conozca el tema. Cuando no tiene criterio formado, no se elige por él en silencio ni se le vuelca una clase teórica: se explica en dos o tres frases qué implica cada opción **para este caso concreto**, se recomienda una con su fundamento, y se sigue.

### Dónde suelen esconderse

No es una lista para recorrer entera en cada trabajo. Es dónde mirar para detectar qué aplica al artefacto que se está por construir.

- **Modo de almacenamiento del modelo semántico.** La más cara de revertir cuando hay un modelo de por medio. Depende del volumen, de la frecuencia con que cambian los datos y de la latencia que tolera quien consume. Tiene además interacciones que conviene verificar antes y no después: Direct Lake no admite columnas calculadas, y la seguridad a nivel de fila sobre las tablas de origen puede cambiar el comportamiento del modo elegido o hacer fallar la consulta.
- **Grano** de cada tabla de hechos, y si hace falta más de uno.
- **Dónde se resuelve cada cálculo derivado**: materializado aguas arriba o expresado como medida. El principio 5 desarrolla el criterio y sus excepciones.
- **Claves sustitutas o naturales**, y qué pasa con las filas cuya clave no resuelve.
- **Dónde viven las dimensiones compartidas** cuando hay más de un modelo que las consume.
- **Estrategia de carga**: completa o incremental. Si es incremental, cuál es la marca de agua y qué pasa cuando una corrida falla a la mitad.
- **Convención de nombres**, barata de fijar al principio e imposible de cambiar después.

### Cómo se respalda una recomendación

Toda afirmación determinante sobre la plataforma —"no se puede X", "conviene A sobre B", un límite de una feature— se respalda con documentación oficial leída, citando la fecha de la página. Las capacidades cambian entre releases, así que una recomendación basada en lo que se sabía hace seis meses puede estar equivocada hoy, y sonar igual de segura.

Si la documentación no lo dice explícitamente, se declara como inferencia propia. Esa distinción es la diferencia entre un diseño fundado y uno que parece fundado.

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
