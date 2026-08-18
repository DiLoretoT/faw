# Instalación

> La instalación anterior —pegar snippets en el `CLAUDE.md` y el
> `settings.local.json` de cada proyecto— queda obsoleta: eso producía
> exactamente el fallo que esta forma de instalar evita (el método escrito
> pero no cargado, skills que no existían como comandos). Ahora FAW es
> un **plugin de Claude Code** y se instala una vez.

## Requisitos

- Claude Code 2.1.129 o posterior
- Python 3.10+ en el PATH (los hooks y verificadores son Python)
- `pip install pyyaml`
- git en el PATH

## 1. Cargar el plugin

**Instalación persistente** (recomendada — no depende de acordarse de un flag).
El repo es su propio marketplace:

```bash
claude plugin marketplace add DiLoretoT/faw
claude plugin install faw@faw
```

También funciona desde un clon local (`claude plugin marketplace add <ruta-del-clon>`),
que es lo que conviene para desarrollar FAW mismo.

Queda a scope user y carga en todas las sesiones. **Es un snapshot**: la copia
vive en `~/.claude/plugins/cache/faw/faw/<version>/`, así que un cambio en el
origen no aplica hasta actualizar:

```bash
claude plugin update faw@faw
```

**Para una sola sesión** (desarrollo del propio FAW, prueba sin instalar):

```bash
claude --plugin-dir <ruta-del-clon>
```

Instalado el plugin quedan registrados, sin más pasos:

- los **4 hooks** (inyección de contexto por turno, compuerta de escritura,
  compuerta de PR, pre-commit de metadata + plataforma),
- las **6 skills** `/faw:faw-*` (clasificar, perfilar, validar, backlog, roadmap,
  arquitectura),
- el **agente** `faw-validador`.

Verificar el manifest cada vez que se toque algo del plugin:

```bash
claude plugin validate <ruta-del-clon>
```

## 2. Activar FAW en un proyecto

Los hooks son **opt-in por proyecto**: no hacen nada salvo que el repo tenga un
directorio `.faw/` en la raíz.

```bash
mkdir .faw
```

Eso es todo. Desde ese momento:

- cada turno recibe el estado del método inyectado (fase, tier, ticket, regla de la fase);
- la primera escritura sin CLASIFICACIÓN registrado se **deniega**;
- los commits pasan por las compuertas `metadata` y `plataforma`;
- los `gh pr create/edit` pasan por el checklist de superficie de cliente.

`.faw/` va al `.gitignore` del proyecto: el estado, los recibos y la config son
artefactos del método, no del entregable — y `config.json` puede declarar nombres
que justamente no deben publicarse.

## 3. Compartirlo con el equipo

El repo incluye `.claude-plugin/marketplace.json`, así que sirve de marketplace
él mismo: cada persona del equipo corre los mismos dos comandos del paso 1 y
queda con la misma versión, actualizable con `claude plugin update faw@faw`.

## 4. La capa de plataforma de Microsoft (complemento, no parte del plugin)

FAW asume disponible `microsoft/skills-for-fabric` — ver
[`faw/reglas/skills-microsoft.md`](../faw/reglas/skills-microsoft.md) para el
estado de instalación híbrido (plugin nativo `powerbi-authoring` + clon local,
`~/skills-for-fabric` en los ejemplos) y las reglas de convivencia con FAW.

```bash
git -C ~/skills-for-fabric pull --ff-only   # si hace >7 días del último
```

## Verificar que funciona

Las tres señales, en orden de rapidez (detalle en GUIA_COMPLETA §10d):

```bash
# 1. La inyección por turno responde para un repo activado (ruta = tu clon/instalación):
echo '{"cwd":"C:/ruta/al/repo"}' | python <ruta-de-faw>/faw/hooks/inyectar_contexto.py

# 2. Los verificadores no se rompieron con el tiempo:
python <ruta-de-faw>/scripts/autoverificar.py

# 3. La prueba de fuego: pedirle a Claude un Write con el estado en IDLE.
#    Tiene que denegarlo citando la clasificación.
```

## Los overrides de un solo uso

Cuando una compuerta de commit bloquea algo **intencional**, el destrabe es un
archivo que se consume solo (no queda como bypass permanente):

| Compuerta | Archivo |
|---|---|
| `metadata` (migración real de lakehouse, etc.) | `.faw/metadata-permitida.txt` con el motivo |
| `plataforma` (ej. sin red para resolver una URL) | `.faw/plataforma-permitida.txt` con el motivo |

## Los límites, dicho acá también

Livy no se puede bloquear honestamente: es código Spark arbitrario. Ahí el
método **detecta, no previene**. Lo mismo aplica hoy a escrituras vía el MCP de
Fabric y a archivos escritos desde `Bash` (heredoc, `>`), que no pasan por el
hook de escritura — están en GUIA_COMPLETA §14 como los huecos siguientes a
cerrar. Un método que prometiera bloquearlos estaría mintiendo sobre una
compuerta.

## Desinstalar / desactivar

- Desactivar en un proyecto: borrar `.faw/` (los hooks vuelven a no hacer nada).
- Descargar el plugin: no pasar `--plugin-dir` (o `claude plugin uninstall faw`
  si se instaló por marketplace).
