# Superficie de cliente

Antes de escribir en cualquier lado: **¿quién lo lee?**

FAW no distingue repos propios de repos de cliente. Todo repo gobernado se trata como
**superficie de cliente**: lo que se escribe ahí lo lee el destinatario del repo — un cliente,
un equipo ajeno, cualquier tercero. La distinción no existe a propósito: es una decisión tomada
una sola vez, que elimina la posibilidad de equivocarla repo por repo.

## El mapa

| Superficie | Quién la lee | Qué puede ir |
|---|---|---|
| Chat con el usuario | Solo el usuario | Todo |
| `docs/faw/` del repo de trabajo | Quien lea el repo | Artefactos del método (la compuerta no los revisa); si el lector no debe verlos, se apuntan fuera del repo con `artefactos_en` |
| Trackers internos del proyecto | Equipo interno | Todo: hallazgos, preguntas, razonamiento |
| **El repo de trabajo** | **El destinatario del repo** | Solo qué cambió y cómo se validó |
| PR, commits, issues de ese repo | **El destinatario** | Ídem |
| Workspace de Fabric | **Quien use el tenant** | Nombres y descripciones de artefactos |
| Documentos y presentaciones | **El cliente** | Entregable, sin metodología interna |

**El caso que se confunde siempre:** un repo remoto se siente espacio de trabajo interno y no
lo es. Todo commit, PR e issue lo lee quien tenga acceso — y en consultoría, ese es el cliente,
en su propia casa.

## Qué nunca va a una superficie de cliente

- **Hablar del cliente en tercera persona.** Escribir "temas para llevar al cliente" en el repo del cliente.
- **Asignar tareas a personas del cliente.** "Confirmar con Contabilidad", "preguntar a Fulano". Eso va al tracker interno y lo lleva el usuario cuando corresponda.
- **Hallazgos abiertos y preguntas de negocio.** Generan preguntas y ruido en un lugar donde nadie va a poder responderlas ni contextualizarlas.
- **Alternativas descartadas y razonamiento de diseño extenso.** Una línea de fundamento por decisión alcanza.
- **Metodología interna.** Reuso de plantillas o marcos propios, nombres de otros clientes o proyectos, referencias a repositorios internos.
- **Atribución de IA.** Ni en commits, ni en cuerpos de PR, ni en comentarios.

## Qué sí va en un PR

1. Qué cambió — tabla de columnas nuevas, artefactos tocados.
2. Una línea de fundamento por decisión no obvia.
3. Números de validación.
4. Nota de despliegue, si el cambio requiere un paso manual.

Nada más. Si el cuerpo pasa de una pantalla, sobra algo.

## Dónde va lo demás

| Contenido | Destino |
|---|---|
| Hallazgos de datos, preguntas para el negocio | Tracker interno del proyecto |
| Razonamiento de diseño completo, alternativas | `docs/faw/<ticket>/diseno.md` (exento de la compuerta), o fuera del repo vía `artefactos_en` si el lector no debe verlo |
| Contratos de datos, perfilados | Ídem — ruta en `.faw/config.json` → `artefactos_en` |
| Decisiones de arquitectura duraderas | Documentación técnica interna del proyecto |
| Aprendizajes portables a otros proyectos | Base de conocimientos |

> Esto vale para **los archivos del repo, no solo para el PR**. Un notebook, el markdown de una
> celda, un `print()` que sale por consola en cada corrida, el texto de un visual de un reporte:
> todo eso lo lee el destinatario igual que un PR. La compuerta `superficie` lo revisa sobre el
> diff antes de cada commit, con `docs/faw/` y `.faw/` como únicas rutas exentas.

## Lo que declara cada proyecto

Los patrones genéricos viven en el código. Lo específico de cada proyecto se declara en
`.faw/config.json` (no se versiona), en dos listas vacías por defecto:

- `personas_cliente`: nombres de personas que no deben aparecer en archivos ni PRs.
- `literales_internos`: nombres de otros clientes, repos o metodología propia que no deben filtrarse.

## La verificación, antes de publicar

Antes de crear un PR o comitear, releer el texto buscando:

- [ ] La palabra "cliente" refiriéndose a quien va a leerlo.
- [ ] Nombres de personas del cliente con una tarea asignada.
- [ ] Secciones de hallazgos, pendientes o preguntas abiertas.
- [ ] Nombres de otros clientes o de repositorios internos.
- [ ] Cualquier mención de asistencia de IA.
- [ ] Más de una pantalla de texto.

Si aparece alguna, se corrige antes de publicar — no después.
