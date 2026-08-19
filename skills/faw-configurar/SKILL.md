---
name: faw-configurar
description: Define el perfil del proyecto — gestor de tickets, ambientes, canales disponibles — y lo escribe en faw.json. Usar la primera vez que se activa FAW en un repositorio, o cuando algo de esa infraestructura cambia.
---

# Configurar el proyecto

FAW funciona sin esta configuración. Lo que cambia es cuánto tiene que suponer.

Sin perfil, el método resuelve cada dato ausente por la opción más estricta: asume que hay un solo ambiente y que es productivo, con lo que toda escritura contra la plataforma exige autorización por escrito antes de ejecutarse. Eso es correcto como default —equivocarse hacia el lado estricto cuesta una autorización de más, hacia el otro lado escribe en producción sin preguntar— pero puede ser más ceremonia de la que el proyecto necesita.

Esta skill hace las preguntas una vez y escribe `faw.json` en la raíz del repositorio.

## Antes de preguntar, mirar

Varias respuestas se pueden deducir del repositorio en vez de preguntarlas. Se deduce, se propone y se confirma; no se pregunta lo que ya está a la vista:

- El remoto de git dice si el proyecto vive en GitHub o en Azure DevOps, que es una pista sobre dónde están los tickets.
- Los servidores MCP conectados en la sesión dicen qué gestores se pueden operar directamente.
- La estructura del repositorio suele mostrar si hay artefactos de Fabric versionados.

## Las preguntas

**1. ¿Dónde viven los tickets?**

Opciones: `ado`, `jira`, `github`, `interno`, `ninguno`.

Si el usuario no usa ninguna herramienta de gestión, o no quiere conectarla, la respuesta es `interno`: FAW lleva el registro en `docs/faw/tickets/`, genera los identificadores y el historial lo aporta git. No hay que instalar nada ni inventar identificadores.

Que exista o no un servidor MCP para la herramienta elegida es un tema aparte y no cambia la respuesta: con MCP el agente consulta y actualiza los tickets; sin MCP, el usuario opera su herramienta y el método usa el identificador que él informe. En los dos casos FAW funciona igual.

**2. ¿Hay un ambiente de desarrollo separado del productivo?**

Es la pregunta que más cambia el comportamiento. Un único workspace es un patrón válido y soportado —Microsoft lo documenta para organizaciones chicas— pero implica que todo lo que se escribe cae sobre datos que alguien está usando.

- **Sí hay ambiente separado**: la autorización para escribir se acuerda conversando en el turno.
- **No, es uno solo**: cada escritura contra la plataforma exige que el motivo quede escrito en `.faw/autorizacion-tenant.txt` antes de ejecutarse. El archivo se consume al usarse.

**3. ¿Cómo se promueve un cambio a producción?**

`deployment-pipeline`, `git`, `manual` o `ninguna`. Los deployment pipelines requieren varios workspaces en la misma capacidad, así que no están disponibles en un despliegue de workspace único.

**4. ¿Se ejecuta código contra la plataforma desde acá?**

Si el proyecto usa sesiones Spark interactivas, se declara. Sin declararlo, el agente no da por sentado que ese canal está disponible: lo propone y el usuario decide.

**5. ¿Hay una tabla de control de corridas?**

Si existe, se declara su nombre y ahí se registra cada ejecución que escribe. Si no, el registro va al recibo del ticket.

## El archivo que se escribe

```json
{
  "tickets": { "sistema": "interno" },
  "ambientes": { "dev": false, "prd": true, "promocion": "manual" },
  "canal": { "livy": false, "tabla_control": null }
}
```

`faw.json` **se versiona**. Son las reglas de proceso del equipo: tienen que viajar con el repositorio, revisarse en un pull request y ser iguales para todos. Un perfil que vive en una sola máquina produce dos personas trabajando bajo reglas distintas sin que nada lo detecte.

## Lo que no va en ese archivo

Nombres de personas, identificadores internos de otros proyectos y rutas locales van en `.faw/config.json`, que no se versiona:

```json
{
  "personas_cliente": ["Apellido"],
  "literales_internos": ["repo-interno"],
  "artefactos_en": "/ruta/a/la/documentacion/interna"
}
```

Las dos primeras listas alimentan la compuerta de superficie, que frena un commit o un pull request que las contenga. `artefactos_en` se usa cuando el razonamiento de diseño no debe quedar en un repositorio que lee un tercero.

## Al terminar

Mostrar el archivo escrito y qué cambia en la práctica, en dos o tres líneas. Si el proyecto ya tenía un `faw.json`, decir explícitamente qué valores cambian antes de escribirlo: cambiar el perfil a mitad de un trabajo abierto altera las reglas bajo las que ese trabajo empezó.
