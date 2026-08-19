---
name: faw-roadmap
description: Contrasta lo planificado contra lo que existe de verdad en la plataforma, y cuando no hay un rumbo definido ayuda a construirlo tomando como referencia el marco de adopción oficial de Microsoft. Usar al revisar avance, al replanificar, o cuando el backlog se quedó sin nada que proponer.
---

# Roadmap

Esta skill hace dos trabajos distintos según lo que el proyecto ya tenga.

Si hay un plan, lo contrasta contra la realidad y muestra las diferencias. Si no hay ninguno, ayuda a construir uno. La segunda situación es más común de lo que parece: un proyecto puede tener un backlog lleno de tareas y aun así no tener rumbo, porque un backlog dice qué hay pendiente y un roadmap dice hacia dónde se va.

---

## Cuando hay un plan: contrastar tres estados

Tres cosas que empiezan iguales y divergen con el tiempo:

1. **Lo planificado** — lo que dice el backlog o el documento de rumbo.
2. **Lo registrado** — lo que el equipo cree que está hecho.
3. **Lo que existe** — lo que hay realmente desplegado en la plataforma.

El material de esta skill son las diferencias. No se esconden ni se suavizan: una discrepancia es información sobre por qué el plan y la realidad se separaron.

| Desvío | Qué significa |
|---|---|
| Hecho pero no cerrado | El trabajo existe y el registro no lo refleja |
| Cerrado pero no hecho | El registro dice terminado y en la plataforma no está, o está a medias |
| Hecho sin planificar | Apareció trabajo que nadie planificó: normalmente urgencias o descubrimientos |
| Planificado hace mucho, sin empezar | Candidato a que ya no haga falta |
| Bloqueado sin dueño | Nadie tiene la acción que lo destraba |
| Construido dos veces | Dos artefactos resuelven lo mismo sin saberlo |

Por cada desvío se dice **la causa**, no solo el hecho: información que llegó tarde, realidad técnica distinta de la esperada, estimación equivocada, o algo que se descubrió al construir. Sin causa, la lista es un inventario; con causa, sirve para decidir.

Verificar contra la plataforma, no contra el repositorio: el repositorio declara la intención y el ambiente desplegado es lo que existe (principio 11).

El resultado no es un informe de avance. La pregunta que responde es si el plan sigue siendo el correcto.

---

## Cuando no hay plan: construir el rumbo

Si el proyecto no tiene roadmap, esta skill lo ofrece en vez de dar el tema por cerrado. No es obligatorio tenerlo: un proyecto chico puede funcionar bien resolviendo pedidos a medida que llegan. Pero conviene que sea una decisión y no un olvido, porque sin rumbo la infraestructura de datos crece por acumulación y cada pieza responde a la urgencia de su momento.

### La referencia: el marco de adopción de Microsoft

Microsoft publica el **Microsoft Fabric adoption roadmap**, que ordena la adopción en doce áreas y define niveles de madurez para ubicarse en cada una. Las áreas son: cultura de datos, patrocinio ejecutivo, alineación con el negocio, propiedad y gestión del contenido, alcance de la distribución, centro de excelencia, gobierno, mentoría y habilitación de usuarios, comunidad de práctica, soporte a usuarios, supervisión del sistema, y gestión del cambio.

*Verificado en Microsoft Learn, página con `ms.date` 2024-12-30. Existe además un "Power BI adoption framework" anterior, orientado a partners; la propia documentación indica que el adoption roadmap es la guía vigente. Cuando se cite este marco, leer la página y usar su fecha.*

**Cómo se usa acá, y cómo no.** Ese marco es organizacional: cubre cultura, patrocinio y gobierno, que se deciden por afuera de cualquier herramienta técnica. FAW no gobierna nada de eso y no debe pretender que sí. Lo que esta skill hace es usarlo como **checklist de rumbo**, para que un roadmap técnico no se arme mirando únicamente la pila de tareas pendientes.

De las doce áreas, las que se traducen a trabajo concreto de ingeniería de datos son cuatro:

| Área del marco | Qué preguntas abre para el roadmap técnico |
|---|---|
| **Propiedad y gestión del contenido** | ¿Quién es dueño de cada artefacto? ¿Qué pasa cuando quien lo construyó no está? |
| **Gobierno** | ¿Hay convención de nombres, capas y permisos, o cada pieza sigue la suya? ¿Los datos sensibles están identificados? |
| **Supervisión del sistema** | ¿Alguien mira el consumo de capacidad, las corridas fallidas, los modelos que no se actualizan? |
| **Alcance de la distribución** | ¿Esto lo usa una persona, un equipo o toda la organización? Cambia lo que hay que construir |

Las otras ocho se mencionan si el usuario quiere ubicarse en el marco completo, pero no se convierten en tickets: no son trabajo de ingeniería.

### Qué se produce

Una propuesta de rumbo corta, con tres a cinco objetivos, y para cada uno: qué problema resuelve, qué habría que construir, y qué lo bloquea hoy. Se ordena por dependencia técnica, igual que el backlog.

El roadmap se guarda en el repositorio, en `docs/faw/roadmap.md`, y se revisa cuando cambia algo relevante, no en una cadencia fija.

**No se crean tickets a partir del roadmap sin el OK del usuario.** Un roadmap aprobado no es autorización para llenar el backlog: es el marco desde el que se proponen los tickets uno por uno.
