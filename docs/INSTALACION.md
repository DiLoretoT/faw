# Instalación

## Requisitos

- Claude Code reciente (los hooks de este método usan matchers sobre herramientas MCP)
- Python 3.10 o posterior en el PATH
- `pip install pyyaml`
- git en el PATH

## 1. Cargar el plugin

```bash
claude plugin marketplace add DiLoretoT/faw
claude plugin install faw@faw
```

Queda instalado a nivel usuario y carga en todas las sesiones. Es una copia: vive en la caché de plugins, así que un cambio en el repositorio de origen no aplica hasta actualizar.

```bash
claude plugin update faw@faw
```

Para desarrollar el propio FAW, o para probarlo sin instalarlo, se puede cargar desde un clon local por una sola sesión:

```bash
claude --plugin-dir <ruta-del-clon>
claude plugin validate <ruta-del-clon>
```

Con el plugin instalado quedan registrados, sin más pasos, los hooks, las skills `/faw:faw-*` y el agente validador.

## 2. Activar FAW en un proyecto

Los hooks son opt-in por proyecto: no hacen nada salvo que el repositorio tenga un directorio `.faw/` en la raíz.

```bash
mkdir .faw
```

Desde ese momento, cada turno recibe el estado del método inyectado; la primera escritura sin trabajo clasificado se deniega; los commits pasan por las compuertas de metadata, plataforma y superficie; los pull requests pasan por el checklist de superficie; y las escrituras contra la plataforma por MCP quedan sujetas a la fase en curso.

`.faw/` va al `.gitignore` del proyecto: el estado, los recibos y la configuración local son artefactos del método, y esa configuración puede contener nombres que no deben publicarse.

## 3. Configurar el proyecto

```
/faw:faw-configurar
```

Define dónde viven los tickets, si hay un ambiente de desarrollo separado del productivo, y qué canales de ejecución están disponibles. El resultado se escribe en `faw.json`, en la raíz del repositorio, y **se versiona**: son reglas de proceso del equipo, no configuración de una máquina.

```json
{
  "tickets": { "sistema": "interno" },
  "ambientes": { "dev": false, "prd": true, "promocion": "manual" },
  "canal": { "livy": false, "tabla_control": null }
}
```

Todo es opcional. Sin este archivo el método funciona igual, resolviendo cada dato ausente por la opción más estricta: un solo ambiente, tratado como productivo, con autorización por escrito antes de cada escritura.

Lo que **no** va en ese archivo son los nombres de personas, los identificadores de otros proyectos y las rutas locales. Eso vive en `.faw/config.json`, que no se versiona:

```json
{
  "personas_cliente": ["Apellido"],
  "literales_internos": ["repo-interno"],
  "artefactos_en": "/ruta/a/la/documentacion/interna"
}
```

Las dos listas alimentan la compuerta de superficie, que frena el commit o el pull request que las contenga. `artefactos_en` se usa cuando el razonamiento de diseño no debe quedar en un repositorio que lee un tercero.

## 4. La capa de plataforma de Microsoft

FAW gobierna el proceso y deja la mecánica de cada artefacto a las skills oficiales, que se instalan aparte. Son dos bundles: el de Power BI no viene incluido en el de Fabric.

```bash
claude plugin marketplace add microsoft/skills-for-fabric
claude plugin install fabric-skills@fabric-collection
claude plugin install powerbi-authoring@fabric-collection
```

Detalle y reglas de convivencia en [`faw/reglas/skills-microsoft.md`](../faw/reglas/skills-microsoft.md).

## Verificar que funciona

```bash
# 1. La inyección por turno responde para un proyecto activado:
echo '{"cwd":"/ruta/al/proyecto"}' | python <faw>/faw/hooks/inyectar_contexto.py

# 2. Los verificadores no se rompieron con el tiempo:
python <faw>/scripts/autoverificar.py

# 3. La prueba de fuego: pedirle a Claude una escritura sin trabajo clasificado.
#    Tiene que denegarla citando la clasificación.
```

La tercera es la que importa. Un hook que se rompe termina con un código de salida distinto de cero, y eso se trata como no bloqueante, así que un hook roto se ve exactamente igual que un hook que aprueba. Se prueban ejecutándolos.

## Los permisos de un solo uso

Cuando una compuerta bloquea algo intencional, el destrabe es un archivo que se consume al usarse, para que una excepción puntual no quede como un permiso permanente que nadie recuerda haber dado.

| Compuerta | Archivo |
|---|---|
| `metadata` | `.faw/metadata-permitida.txt` con el motivo |
| `plataforma` | `.faw/plataforma-permitida.txt` con el motivo |
| `superficie` | `.faw/superficie-permitida.txt` con el motivo |
| Escritura contra la plataforma, en proyectos de ambiente único | `.faw/autorizacion-tenant.txt` con la operación y el motivo |

Los hooks corren **antes** del comando, así que escribir el archivo y ejecutar la acción en la misma llamada no funciona: cuando el hook mira, el archivo todavía no existe. Van en dos pasos.

## Los límites

El código arbitrario que corre dentro de una sesión Spark no se puede inspeccionar antes de que se ejecute, y los archivos escritos desde la terminal con redirección o documentos embebidos no pasan por el hook de escritura. Ahí el método detecta, no previene. Un método que prometiera bloquearlos estaría mintiendo sobre una compuerta.

## Desinstalar

- Desactivar en un proyecto: borrar `.faw/`, y los hooks vuelven a no hacer nada.
- Quitar el plugin: `claude plugin uninstall faw`.
