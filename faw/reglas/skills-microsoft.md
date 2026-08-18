# La capa de plataforma: microsoft/skills-for-fabric

FAW gobierna el **proceso** (fases, compuertas, calidad). No enseña a escribir un Eventstream ni cuál API usar para desplegar un modelo semántico — y no debe: ese conocimiento cambia con cada release de Fabric y mantenerlo a mano garantiza que envejezca mal.

Esa capa existe y la mantiene Microsoft: [`microsoft/skills-for-fabric`](https://github.com/microsoft/skills-for-fabric) (MIT). Skills operativas por tipo de artefacto, escritas por el fabricante, con decision trees de qué herramienta usar (MCP > CLI > API) y patrones verificados.

**Las dos capas se complementan y no se pisan** — verificado leyendo su propio repo: se declara "primarily artifact-authoring focused" y explícitamente sin compuertas formales ni contratos de datos. Eso lo pone FAW.

## Dónde vive y cómo se actualiza

Clon local, en la ruta que prefieras (en los ejemplos, `~/skills-for-fabric`) — canal de instalación **soportado oficialmente** por el repo (su skill `check-updates` lo trata como "Git channel" de primera clase).

```bash
git -C ~/skills-for-fabric pull --ff-only
```

**Cadencia:** al arrancar trabajo Fabric, si hace más de 7 días del último pull, actualizar y mirar el `CHANGELOG.md` por cambios relevantes. (Espeja el "network guard" de 7 días que usa su propio `check-updates`.) Nunca editar nada dentro del clon: es de Microsoft, se consume tal cual.

## Cuándo consultar qué

En **CONSTRUCCIÓN**, antes de autorizar un tipo de artefacto, leer la skill correspondiente:

| Vas a trabajar en… | Leé |
|---|---|
| Notebook Spark / Lakehouse / MLV | `plugins/fabric-authoring/skills/spark-authoring-cli/SKILL.md` + `common/notebook-authoring/` |
| Modelo semántico (crear, medidas, relaciones, deploy, refresh) | `plugins/powerbi-authoring/skills/semantic-model-authoring/SKILL.md` |
| Reporte Power BI (planificar / diseñar / autorizar / gestionar) | `plugins/powerbi-authoring/skills/powerbi-report-*/SKILL.md` |
| Dataflows Gen2 | `plugins/fabric-authoring/skills/dataflows-authoring-cli/SKILL.md` |
| Warehouse / SQL endpoint | `plugins/fabric-authoring/skills/sqldw-authoring-cli/SKILL.md` |
| Diagnóstico de jobs Spark / performance | `plugins/fabric-operations/` (bundle completo en el manifest) |
| Arquitectura medallion end-to-end | `plugins/fabric-authoring/skills/e2e-medallion-architecture/SKILL.md` |

## Los agentes de Microsoft son subagentes reales

`agents/FabricDataEngineer.agent.md` y compañía tienen el formato exacto de un subagente de Claude Code (frontmatter + reglas de delegación hacia sus skills). Se usan como subagentes vía **wrappers locales** en `~/.claude/agents/` (ej.: `fabric-data-engineer.md`), que:

- apuntan a la definición canónica **dentro del clon** (así `git pull` los actualiza sin tocar el wrapper);
- traducen las referencias a skills en rutas del clon;
- agregan las reglas de la casa que prevalecen si chocan: **un subagente no puede obtener el OK de escritura — si su tarea requiere escribir, devuelve la operación propuesta al orquestador para aprobación del usuario**; el canal de cambio lo gobierna FAW, no la skill.

Nunca editar los archivos del clon: el wrapper existe justamente para no hacerlo.

## Reglas de convivencia con FAW

1. **FAW manda en proceso; skills-for-fabric manda en mecánica.** Si su skill dice "deploy directo al workspace" y FAW dice "por PR", gana FAW: sus skills no conocen nuestro canal de cambio ni la superficie de cliente.
2. **Sus skills no saben de autorización por turno.** Cualquier operación de escritura que una skill de Microsoft proponga sigue necesitando el OK explícito del turno. La skill dice *cómo*; el permiso lo da el usuario.
3. **Sus decision trees de herramienta sí se adoptan** (ej.: preferir `powerbi-modeling-mcp` sobre editar TMDL a mano) — es exactamente el tipo de conocimiento de plataforma que no queremos mantener nosotros.
4. **Es una fuente citable de mecánica, no de comportamiento del producto.** Para afirmaciones determinantes ("no se puede X") sigue rigiendo la regla de doc oficial leída con `ms.date` — una skill puede estar desactualizada igual que un blog.

## Estado de instalación: híbrido, y el porqué exacto

- **`powerbi-authoring@fabric-collection` instalado como plugin nativo** (scope user, v0.3.10). Sus 6 skills (semantic-model-authoring + powerbi-report-*) cargan nativamente, su `check-updates` avisa solo, y declara el MCP `powerbi-modeling-mcp` (stdio).
- **Los bundles de Fabric (`fabric-authoring`, `fabric-skills`, etc.) NO se pudieron instalar como plugin**: declaran un MCP de tipo **HTTP** (`fabric-sqlendpoint` → `api.fabric.microsoft.com`) y Claude Code 2.1.220 rechaza plugins con MCPs HTTP ("source type not supported"). Verificado instalando: `powerbi-authoring` (MCP stdio) entró; `fabric-authoring` (MCP http) no. **Reintentar tras cada update de Claude Code** — cuando entre, sus skills y sus 3-4 agentes se registran solos y los wrappers locales quedan redundantes.
- **Mientras tanto, las skills de Fabric se consumen del clon** (tabla de arriba) — canal Git soportado de primera clase por su propio `check-updates`.
- El MCP `fabric-sqlendpoint` **se agregó a mano** (`claude mcp add --transport http --scope user ...`): consultas T-SQL al SQL endpoint sin levantar sesión Livy (segundos vs. minutos, para lecturas de perfilado/validación). Requiere autenticarse la primera vez vía `/mcp` en sesión interactiva, y aplica el mismo gotcha de tenant que `ms-fabric-mcp`: verificar contra qué tenant quedó la sesión antes de usarlo con un cliente.

Los plugins y MCPs instalados a nivel user recién aparecen en sesiones nuevas (o tras `/reload-plugins`).
