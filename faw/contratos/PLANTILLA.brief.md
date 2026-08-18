# Brief de reporte — <TICKET>

> Se llena **con el usuario**, en CLASIFICACIÓN, antes de escribir una linea del PBIR.
> No se deduce leyendo el modelo semantico: el modelo dice que datos hay, no que
> decision tiene que habilitar el reporte ni quien la toma.
> Lo verifica `scripts/verificar_brief.py`, que rechaza el template sin llenar.

## Objetivo

<Para que existe este reporte. Que decision habilita, o que pregunta cierra.
Si la respuesta es "para ver los datos", todavia no hay objetivo: eso es una
exploracion, y va con tier EXPLORACION.>

## Audiencia

<Quien lo va a abrir, con que rol, y con que frecuencia. Un nombre y un rol
concretos, no "el negocio". Si es de uso interno del equipo tecnico, decirlo
explicito: cambia el nivel de pulido y las reglas de superficie de cliente.>

## Preguntas que responde

<Al menos tres, cada una terminada en signo de interrogacion. Son el criterio de
aceptacion: si el reporte no las contesta, no esta listo, aunque se vea bien.>

1. <...?>
2. <...?>
3. <...?>

## Fuera de alcance

<Que NO entra. Esta seccion es la que evita que el reporte crezca solo, y es la
que mas se salta.>

## Origen de datos

<Modelo semantico, workspace, tipo de conexion y tablas que se consumen. Si el
reporte necesita una medida o una columna que todavia no existe, es un trabajo
de tier MODELO o ARTEFACTO aparte: se anota aca y se clasifica por separado.>

## Validacion de negocio

<Quien confirma que los numeros estan bien. Nombre concreto. Si no hay nadie
identificado, el reporte se puede construir pero **no se publica como
productivo** — se marca como exploratorio y queda registrado que la
reconciliacion esta pendiente.>
