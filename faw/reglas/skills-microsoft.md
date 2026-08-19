# La capa de plataforma: skills oficiales de Microsoft

FAW gobierna el **proceso**: qué se verifica, en qué orden, con qué evidencia. No enseña a escribir un Eventstream ni cuál API despliega un modelo semántico, y no debe: ese conocimiento cambia con cada release de Fabric, y mantenerlo a mano garantiza que envejezca mal sin que nadie lo note.

Esa capa la mantiene Microsoft en [`microsoft/skills-for-fabric`](https://github.com/microsoft/skills-for-fabric): skills operativas por tipo de artefacto, escritas por el fabricante, con árboles de decisión sobre qué herramienta usar para cada operación.

**Las dos capas se complementan porque resuelven cosas distintas.** El propio repo de Microsoft se declara enfocado en la autoría de artefactos y sin compuertas formales ni contratos de datos. Eso es lo que pone FAW.

## Instalación

Se instala como plugin, igual que FAW. Son **dos bundles separados**: el de Power BI no viene incluido en el de Fabric.

```bash
claude plugin marketplace add microsoft/skills-for-fabric
claude plugin install fabric-skills@fabric-collection
claude plugin install powerbi-authoring@fabric-collection
```

También se puede consumir desde un clon local del repositorio, que es la vía para editores que no soportan plugins. Si se usa un clon, la ruta se declara en `faw.json` bajo `canal.skills_microsoft`, y conviene actualizarlo periódicamente: una skill de plataforma desactualizada es peor que no tenerla, porque afirma con seguridad algo que dejó de ser cierto.

```bash
git -C <ruta-del-clon> pull --ff-only
```

## Qué skill leer, y por qué no hay una tabla exhaustiva acá

El repositorio de Microsoft reorganiza sus skills entre versiones: fusiona bundles, renombra carpetas y elimina las que deja de mantener. Una tabla de rutas copiada en este archivo queda desactualizada sin que nada avise, y el método terminaría mandando a leer archivos que ya no existen.

**El índice se consulta en el repositorio instalado**, que es la única fuente que no envejece. La orientación general, estable entre versiones:

| Vas a trabajar en | Buscá la skill de |
|---|---|
| Notebooks Spark, lakehouse | Spark |
| Modelo semántico: tablas, medidas, relaciones, despliegue, actualización | Autoría de modelo semántico |
| Reporte de Power BI | Planificación, autoría, diseño y gestión de reportes (son skills distintas) |
| Warehouse, SQL | Warehouse y base de datos SQL |
| Dataflows | Dataflows |
| Eventhouse, Eventstream, Activator | Cada uno tiene la suya |
| Versionado e integración con git | Integración con git |
| Promoción entre ambientes | Deployment pipelines |
| Parametrización por ambiente | Variable library |
| Arquitectura medallón de punta a punta | Arquitectura medallón |

Verificado contra el repositorio el 2026-08-19. Si una ruta no resuelve, el índice del repositorio manda sobre esta tabla.

## Los servidores MCP que declara

El repositorio declara servidores MCP propios para consultar el endpoint SQL y para el catálogo de Fabric, y el bundle de Power BI declara uno para modelado. Antes de usarlos conviene tener presente la distinción que hace la propia documentación de Microsoft:

- Los servidores **remotos** de Fabric y Power BI están pensados para consulta y para operaciones de gestión con autenticación y registro de auditoría propios.
- Los servidores **locales** son los que pueden **escribir** un modelo semántico completo.
- El endpoint SQL es de solo lectura por construcción: no admite modificaciones de datos.

Microsoft advierte explícitamente que un cliente MCP autónomo o mal configurado puede ejecutar operaciones destructivas, y que los mecanismos para impedirlo no están estandarizados en la especificación. Esa es la razón por la que FAW pone su propia compuerta sobre las escrituras por MCP (`faw/hooks/compuerta_mcp.py`) en vez de confiar en el servidor.

## Reglas de convivencia

1. **FAW manda en proceso; las skills de Microsoft mandan en mecánica.** Si una skill dice "desplegar directo al workspace" y FAW dice "por PR", gana FAW: esas skills no conocen el canal de cambio del proyecto ni quién lee cada superficie.
2. **Ninguna operación de escritura que una skill proponga exime del OK del turno.** La skill dice *cómo*; el permiso lo da el usuario.
3. **Sus árboles de decisión de herramienta sí se adoptan.** Es exactamente el tipo de conocimiento de plataforma que no conviene mantener por afuera.
4. **Son fuente de mecánica, no de comportamiento del producto.** Para una afirmación determinante ("no se puede X") sigue rigiendo el principio 6: documentación oficial leída, con la fecha de la página. Una skill puede estar desactualizada igual que cualquier otro texto.
5. **Nunca editar los archivos del clon.** Se consumen tal cual; lo que se quiera cambiar se resuelve del lado de FAW.
