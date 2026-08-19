# FAW — Fabric Agentic Workflow

Un método de trabajo para agentes de IA que construyen soluciones de datos sobre Microsoft Fabric. Fases en orden, compuertas verificadas por scripts, y hooks que las hacen cumplir fuera del modelo: el agente no puede saltárselas por olvido, y saltárselas a propósito deja rastro.

## Por qué

En software, lo que falla se rompe ruidosamente. En una plataforma de datos, el fallo característico es un número creíble y falso: una tabla publicada con menos columnas de las que declara, validada porque el conteo de filas daba bien; una relación que apunta a la columna equivocada y devuelve totales plausibles; una clave foránea nula que hace desaparecer partidas al filtrar, sin ningún error.

Ninguno de esos casos lo detecta un test, un analizador estático o una revisión de código. Se detectan midiendo contra datos reales, y solo si alguien se acuerda de medir. FAW existe para que esa medición no dependa de que alguien se acuerde.

Cada regla del método cierra una vía concreta por la que un dato incorrecto llega a producción sin hacer ruido. Una regla que no se puede atar a un modo de fallo específico no pertenece al método.

## Cómo funciona

Todo pedido se clasifica en un tier, y el tier decide cuánto proceso paga: una consulta se responde y termina; un ajuste de tres líneas no recorre las seis fases; una tabla nueva sí.

```
CLASIFICACIÓN → PERFILADO → DISEÑO → CONSTRUCCIÓN → VALIDACIÓN → PUBLICACIÓN
```

Tres ideas sostienen el resto:

**Evidencia antes que declaración.** Un número sin la consulta que lo produjo no es un dato. La fase de perfilado, que un flujo de desarrollo de software no tiene, existe porque en datos buena parte de los requisitos se descubren midiendo.

**Compuertas con recibos.** Cada verificador, al pasar, emite un recibo con el hash de lo que verificó; la máquina de estados los recomputa, y un recibo vencido cierra la compuerta. Las compuertas que son solo una declaración del agente están marcadas como tales, porque una compuerta a la que se le puede mentir sin avisar convierte a las demás en sugerencias.

**Hooks fuera del modelo.** Instalado como plugin de Claude Code, FAW inyecta el estado en cada turno, deniega escrituras sin clasificación previa, revisa cada commit y cada pull request antes de que existan, e intercepta las escrituras contra la plataforma hechas por servidores MCP.

## Empezar

```bash
claude plugin marketplace add DiLoretoT/faw
claude plugin install faw@faw
```

Activar en un proyecto, que es lo único que hace que los hooks actúen:

```bash
mkdir .faw
```

Después, `/faw-configurar` para declarar dónde viven los tickets y si hay un ambiente de desarrollo separado del productivo. No es obligatorio: sin esa configuración el método asume lo más estricto, que es un solo ambiente tratado como productivo.

## Funciona sin el resto de tus herramientas

No hace falta un gestor de tickets: si no se declara ninguno, FAW lleva el registro en el propio repositorio y genera los identificadores. Si hay uno con servidor MCP conectado, lo consulta y lo actualiza; si lo hay sin MCP, trabaja con el identificador que le pases.

No hace falta un ambiente de desarrollo separado. Un único workspace es un patrón soportado, y en ese caso el método endurece las reglas de escritura en vez de asumir que hay dónde equivocarse barato.

## Qué atrapa cada compuerta

| Verificador | Atrapa |
|---|---|
| `verificar_contrato.py` | Una tabla publicada con menos columnas de las que declara |
| `verificar_modelo.py` | Relaciones invertidas, modo de almacenamiento equivocado |
| `verificar_diff.py` | El commit "de formato" que además borra configuración |
| `verificar_plataforma.py` | Un literal de sintaxis inventado por analogía |
| `verificar_brief.py` | Un reporte construido sin acordar objetivo y audiencia |
| `verificar_reporte.py` | El filtro de desarrollo olvidado y persistido |
| `autoverificar.py` | Que los propios verificadores no se hayan roto con el tiempo |

**Los límites, sin adornos:** el código arbitrario que corre dentro de una sesión Spark y los archivos escritos desde la terminal no pasan por ningún hook. Ahí el método detecta, no previene. Está documentado en [`GUIA_COMPLETA.md`](GUIA_COMPLETA.md) en vez de prometido.

## Documentación

| Documento | Qué es |
|---|---|
| [`GUIA_COMPLETA.md`](GUIA_COMPLETA.md) | El canónico: método, mecánica interna, ciclo con comandos, instalación |
| [`docs/INSTALACION.md`](docs/INSTALACION.md) | Instalación paso a paso, configuración, verificación |
| [`faw/reglas/`](faw/reglas/) | Lo que el agente lee: principios, fases, superficie, capa de plataforma |

## Origen

FAW está inspirado en **[Dilux Agentic Workflow (DAW)](https://github.com/soydiloreto/dilux-agentic-workflow)**, un método de fases con compuertas para pipelines de desarrollo de software. De ahí vienen cuatro ideas que sostienen todo lo demás:

- Fases con compuertas **aplicadas fuera del modelo**, para que no dependan de que el agente se acuerde.
- **Tiers**, para no cobrarle a un ajuste de tres líneas el proceso de una tabla nueva.
- La **escala honesta de fuerza** de cada compuerta: decir cuál se puede satisfacer con una declaración y cuál no.
- Que **valide quien no construyó**.

Lo que cambia es el objeto que se verifica. DAW comprueba que el código compile y que los tests pasen; FAW comprueba que una tabla tenga las columnas que dice tener y que un modelo semántico apunte a donde dice apuntar. La diferencia importa porque los modos de fallo no se parecen: el software roto grita, el dato incorrecto no.

Hay una quinta cosa que FAW toma de DAW y que no es una funcionalidad sino una forma de trabajar: **el método se construye de forma iterativa e incremental, usándolo**. Cada regla que existe llegó porque algo falló de una manera concreta y quedó claro qué habría hecho falta para atajarlo. Ninguna se agregó porque sonara prolija.

La mecánica de plataforma no vive acá a propósito: la mantiene Microsoft en [`skills-for-fabric`](https://github.com/microsoft/skills-for-fabric), y FAW la consume como capa complementaria. FAW manda en proceso, esas skills mandan en mecánica.

## Esto está en construcción, y el feedback es lo que lo hace crecer

FAW no está terminado ni pretende estarlo. Es un método que gana valor a medida que se usa contra situaciones reales: cada proyecto distinto expone un supuesto que no era universal, un fallo que ninguna compuerta atajaba, o una regla que resultó más rígida de lo que el problema pedía. La sección de límites conocidos de la [guía](GUIA_COMPLETA.md) está escrita para que se vea qué falta, en vez de disimularlo.

**El aporte más útil que podés hacer es contar un fallo concreto.** No hace falta que propongas la solución: el método tiene una regla que se aplica a sí mismo, y es que una regla sin un modo de fallo específico detrás no entra. Entonces lo valioso es la otra mitad, la que solo tiene quien lo vivió:

- Un dato incorrecto que llegó a producción sin hacer ruido, y qué lo habría detectado.
- Una compuerta que te frenó sin motivo, o que te dejó pasar algo que no debía.
- Un supuesto de FAW que no aplica a cómo trabaja tu equipo.
- Una afirmación sobre la plataforma que esté desactualizada o directamente mal.

Las issues y los pull requests son bienvenidos. Si algo del método te resultó confuso al leerlo, eso también es un reporte válido: la documentación que no se entiende es documentación que no se cumple.

## Licencia

[Apache-2.0](LICENSE)
